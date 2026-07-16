"""
User Profile Service - per-user structured profile (画像).

Each user has a single UserProfile with:
  - Static fields (display_name, profession, location, language_preference)
  - Dynamic fields (interests, expertise, preferences, topic_history)
  - LLM-generated natural language portrait_summary
  - Auto-update bookkeeping (auto_update_enabled, analyzed_msg_count)

Storage is delegated to a ProfileStore (Protocol):
  - FileProfileStore  -> CLI, persists to ~/.xbots/<os_user>/profile.json
  - DBProfileStore    -> web, persists to user_profiles table

LLM analysis merges new signals into the existing profile; never overwrites
with empty/null unless explicitly stated. Designed to be conservative.
"""
from __future__ import annotations

import json
import logging
import os
from string import Template
import re
import getpass
import asyncio
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


# ─── Data model ──────────────────────────────────────────────────────────


@dataclass
class UserProfile:
    """Structured representation of a user for personalisation."""

    user_id: str

    # Static / demographic
    display_name: str = ""
    profession: str = ""
    location: str = ""
    language_preference: str = "zh-CN"

    # Dynamic
    interests: List[str] = field(default_factory=list)
    expertise: Dict[str, str] = field(default_factory=dict)        # area -> level
    preferences: Dict[str, Any] = field(default_factory=dict)       # style / format etc.
    topic_history: List[Dict[str, Any]] = field(default_factory=list)  # [{topic, weight, last_seen}]

    # LLM-generated
    portrait_summary: str = ""
    portrait_updated_at: Optional[str] = None

    # Source / bookkeeping
    auto_update_enabled: bool = True
    analyzed_msg_count: int = 0
    last_analyzed_at: Optional[str] = None

    # Meta
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserProfile":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean)

    def to_context_string(self, max_chars: int = 1200) -> str:
        """Compact natural-language portrait, designed for system prompt injection.

        Kept under ~1200 chars / ~300 tokens so it doesn't bloat the prompt.
        Empty fields are skipped silently.
        """
        parts: List[str] = []

        identity_bits: List[str] = []
        if self.display_name:
            identity_bits.append(f"display name: {self.display_name}")
        if self.profession:
            identity_bits.append(f"profession: {self.profession}")
        if self.location:
            identity_bits.append(f"location: {self.location}")
        if identity_bits:
            parts.append("- Identity: " + "; ".join(identity_bits))

        if self.language_preference:
            parts.append(f"- Language preference: {self.language_preference}")

        if self.interests:
            tag_list = ", ".join(self.interests[:12])
            parts.append(f"- Interests: {tag_list}")

        if self.expertise:
            level_rank = {"advanced": 0, "intermediate": 1, "beginner": 2}
            top = sorted(
                self.expertise.items(),
                key=lambda kv: (level_rank.get(kv[1], 3), kv[0]),
            )[:8]
            exp_str = ", ".join(f"{k} ({v})" for k, v in top)
            parts.append(f"- Expertise: {exp_str}")

        if self.preferences:
            kv_str = ", ".join(f"{k}={v}" for k, v in list(self.preferences.items())[:6])
            parts.append(f"- Style preferences: {kv_str}")

        if self.topic_history:
            sorted_topics = sorted(
                self.topic_history,
                key=lambda t: (-int(t.get("weight", 0)), str(t.get("last_seen", ""))),
            )[:6]
            topic_str = ", ".join(str(t.get("topic", "")) for t in sorted_topics if t.get("topic"))
            if topic_str:
                parts.append(f"- Recent topics: {topic_str}")

        if self.portrait_summary:
            parts.append(f"- Portrait: {self.portrait_summary[:400]}")

        text = "\n".join(parts)
        if len(text) > max_chars:
            text = text[: max_chars - 3] + "..."
        return text


# ─── Storage interface ───────────────────────────────────────────────────


class ProfileStore(Protocol):
    """Abstract storage backend. Implemented by file / DB stores."""
    def load(self) -> Optional[UserProfile]: ...
    def save(self, profile: UserProfile) -> None: ...
    def delete(self) -> None: ...
    @property
    def user_id(self) -> str: ...


# ─── LLM analysis prompt ─────────────────────────────────────────────────


PROFILE_ANALYSIS_PROMPT = """You are a user profile analyst.

Given the user's recent messages and their current profile, produce an UPDATED profile JSON.

# Current profile (may be partial / empty)
${current_profile_json}

# User's recent messages (chronological, oldest first)
${messages_text}

# Output schema (strict JSON, output ONLY this object, no other text)

{{
  "display_name": "<string or null>",
  "profession":   "<string or null>",
  "language_preference": "zh-CN" | "en-US" | "mixed" | null,
  "interests":    ["<topic tag>", ...],          // max 10, deduped
  "expertise":    {{"<area>": "beginner|intermediate|advanced"}},  // areas they have demonstrated tool in
  "preferences":  {{"<key>": "<value>"}},        // response_style / code_format / response_length / language etc.
  "topic_history": [{{"topic": "...", "weight": 1-5, "last_seen": "ISO8601"}}],
  "portrait_summary": "<1-3 sentence natural-language portrait>"
}}

# Inference rules

- INFER conservatively. Only include things with STRONG signal across multiple messages.
- If uncertain, return null (or omit the key) rather than guessing.
- `portrait_summary` should be useful for PERSONALISATION, not a generic bio.
  - GOOD: "Backend engineer working on a Rust-based rule engine; prefers concise answers with code."
  - BAD:  "User asked some technical questions."
- `interests` should be DISTINCT topics, not redundant synonyms.
- `expertise` should reflect DEMONSTRATED tool, not aspirational.
- `topic_history` weight 5 = primary focus this month, 1 = brief mention.
- Output strictly valid JSON. No markdown, no commentary.
"""


# ─── Service ─────────────────────────────────────────────────────────────


class UserProfileService:
    """Owns the profile lifecycle: load, manual update, LLM analysis."""

    def __init__(
        self,
        store: ProfileStore,
        llm_service: Any = None,
        model: Optional[str] = None,
    ):
        self.store = store
        self.llm_service = llm_service
        self.model = model or "deepseek:deepseek-chat"

    # ── Read / write ────────────────────────────────────────────────
    def get_or_create(self) -> UserProfile:
        p = self.store.load()
        if p is None:
            now = _now_iso()
            p = UserProfile(
                user_id=self.store.user_id,
                created_at=now,
                updated_at=now,
            )
            self.store.save(p)
        return p

    def update(self, partial: Dict[str, Any]) -> UserProfile:
        """Apply a manual partial update. Skips unknown keys."""
        p = self.get_or_create()
        for k, v in (partial or {}).items():
            if hasattr(p, k):
                setattr(p, k, v)
        p.updated_at = _now_iso()
        self.store.save(p)
        return p

    def reset(self) -> UserProfile:
        """Wipe profile to default; preserves user_id and timestamps."""
        now = _now_iso()
        p = UserProfile(
            user_id=self.store.user_id,
            created_at=now,
            updated_at=now,
        )
        self.store.save(p)
        return p

    def set_auto_update(self, enabled: bool) -> UserProfile:
        return self.update({"auto_update_enabled": bool(enabled)})

    # ── Prompt context ──────────────────────────────────────────────
    def build_context_string(self) -> str:
        """Return the prompt-injection block (empty string if no profile data)."""
        p = self.get_or_create()
        return p.to_context_string()

    # ── LLM analysis ────────────────────────────────────────────────
    async def analyze_and_update(
        self,
        new_messages: List[Dict[str, str]],
        force: bool = False,
    ) -> Optional[UserProfile]:
        """Run LLM analysis on `new_messages`, merge into profile, save.

        Returns updated profile, or None if:
          - auto_update is disabled (unless force=True)
          - no llm_service configured
          - new_messages is empty
          - LLM call / parse fails
        """
        p = self.get_or_create()

        if not force and not p.auto_update_enabled:
            return None
        if self.llm_service is None:
            return None
        if not new_messages:
            return None

        current_json = json.dumps(p.to_dict(), ensure_ascii=False, indent=2)
        messages_text = _format_messages(new_messages)

        prompt = Template(PROFILE_ANALYSIS_PROMPT).safe_substitute(
            current_profile_json=current_json,
            messages_text=messages_text,
        )

        try:
            # This service is called from an asyncio background task after a
            # chat response. The SDK's non-streaming client is synchronous, so
            # move it off the web worker's event loop.
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm_service.call_model_with_tools,
                    messages=[{"role": "user", "content": prompt}],
                    tools=None,
                    model=self.model,
                    stream=False,
                    max_tokens=2000,
                ),
                timeout=45,
            )
            content = (resp.get("content", "")
                       if isinstance(resp, dict) else str(resp)).strip()
        except Exception as e:
            logging.warning(f"profile analysis LLM call failed: {e}")
            return None

        data = _safe_json_loads(content)
        if not data:
            logging.warning(f"profile analysis JSON parse failed; raw={content[:300]}")
            return None

        p = self._merge_analysis(p, data, msg_count=len(new_messages))
        try:
            self.store.save(p)
        except Exception as e:
            logging.warning(f"profile save failed: {e}")
            return None
        return p

    @staticmethod
    def _merge_analysis(
        p: UserProfile,
        data: Dict[str, Any],
        msg_count: int,
    ) -> UserProfile:
        now = _now_iso()

        # Scalar fields: only overwrite if new value is truthy
        for field_name in ("display_name", "profession"):
            v = (data.get(field_name) or "").strip()
            if v:
                setattr(p, field_name, v[:128])

        lang = (data.get("language_preference") or "").strip()
        if lang in ("zh-CN", "en-US", "mixed"):
            p.language_preference = lang

        # interests: merge unique, cap at 20
        new_interests = data.get("interests") or []
        if isinstance(new_interests, list):
            cleaned = [str(x).strip() for x in new_interests if str(x).strip()]
            merged = list(dict.fromkeys(list(p.interests) + cleaned))
            p.interests = merged[:20]

        # expertise: keep stronger level
        LEVEL_RANK = {"beginner": 1, "intermediate": 2, "advanced": 3}
        new_exp = data.get("expertise") or {}
        if isinstance(new_exp, dict):
            for area, level in new_exp.items():
                if not isinstance(area, str) or not area.strip():
                    continue
                level_s = str(level).strip().lower()
                if level_s not in LEVEL_RANK:
                    continue
                existing = p.expertise.get(area)
                if (existing is None
                        or LEVEL_RANK[level_s] > LEVEL_RANK.get(existing, 0)):
                    p.expertise[area] = level_s

        # preferences: shallow merge
        new_prefs = data.get("preferences") or {}
        if isinstance(new_prefs, dict):
            merged = dict(p.preferences)
            for k, v in new_prefs.items():
                merged[str(k)] = v
            p.preferences = merged

        # topic_history: merge by topic name
        new_topics = data.get("topic_history") or []
        if isinstance(new_topics, list):
            topic_map = {t.get("topic"): t for t in p.topic_history if t.get("topic")}
            for t in new_topics:
                if not isinstance(t, dict):
                    continue
                topic = str(t.get("topic") or "").strip()
                if not topic:
                    continue
                try:
                    weight = int(t.get("weight", 1))
                except (TypeError, ValueError):
                    weight = 1
                weight = max(1, min(5, weight))
                last_seen = str(t.get("last_seen") or now)
                existing = topic_map.get(topic)
                if existing:
                    existing["weight"] = max(int(existing.get("weight", 0)), weight)
                    existing["last_seen"] = last_seen
                else:
                    topic_map[topic] = {"topic": topic, "weight": weight, "last_seen": last_seen}
            sorted_topics = sorted(
                topic_map.values(),
                key=lambda t: (-int(t.get("weight", 0)), str(t.get("last_seen", ""))),
            )
            p.topic_history = sorted_topics[:20]

        # portrait
        portrait = (data.get("portrait_summary") or "").strip()
        if portrait:
            p.portrait_summary = portrait[:1000]
            p.portrait_updated_at = now

        p.analyzed_msg_count = (p.analyzed_msg_count or 0) + max(0, msg_count)
        p.last_analyzed_at = now
        p.updated_at = now
        return p


# ─── Helpers ─────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_default_user_id() -> str:
    """Return OS-level username (sanitised). Used by FileProfileStore."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", user) or "default"


def _format_messages(messages: List[Dict[str, str]]) -> str:
    """Format messages for the analysis prompt. Truncate each entry."""
    lines: List[str] = []
    for m in messages:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 800:
            content = content[:800] + "..."
        lines.append(f"[{role}] {content}")
    return "\n".join(lines) if lines else "(no messages)"


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON parse. Strips code fences and finds the first {...} block."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl > 0:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to locate first {...} block (greedy from first `{` to last `}`)
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        candidate = text[s:e + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None
