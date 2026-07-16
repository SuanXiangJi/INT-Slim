# -*- coding: utf-8 -*-
"""
Reflection Store
================

Persistent reflection memory store using TF-IDF retrieval.
Reuses the same tokenizer and scoring approach as rag_service.py
for consistency and simplicity (no external vector DB needed).

Reflections are written to the current conversation and also to a user-level
global log, so useful strategy hints can transfer across conversations.
"""
import os
import re
import math
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


# Storage root for reflection logs
REFLECTION_ROOT = Path(__file__).parent.parent.parent / "sandbox" / "reflections"


@dataclass
class ReflectionEntry:
    """A single self-reflection / evaluation record."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    task_summary: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    feedback: str = ""
    action_plan: str = ""
    strategy_hint: str = ""
    tool_history: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionEntry":
        return cls(**data)

    def searchable_text(self) -> str:
        """Concatenate fields that should participate in TF-IDF search."""
        parts = [
            self.task_summary,
            self.feedback,
            self.action_plan,
            self.strategy_hint,
        ]
        return "\n".join(parts)


class ReflectionStore:
    """Reflection memory backed by MySQL + in-process TF-IDF."""

    def __init__(self, user_id: bytes, conversation_id: str):
        self.user_id = user_id
        self.conversation_id = conversation_id

        user_hex = self._user_id_hex()
        conv_dir_name = conversation_id[:16]
        self.user_dir = REFLECTION_ROOT / user_hex
        self.store_dir = self.user_dir / conv_dir_name
        self.global_dir = REFLECTION_ROOT / user_hex / "_global"

        self.reflections_file = self.store_dir / "reflections.json"
        self.global_reflections_file = self.global_dir / "reflections.json"
        self.entries: List[ReflectionEntry] = []
        self.global_entries: List[ReflectionEntry] = []
        self._load()

    def _user_id_hex(self) -> str:
        import binascii
        return binascii.hexlify(self.user_id).decode("ascii")

    def _load(self):
        """Load reflections from MySQL, with a legacy JSON fallback."""
        try:
            from app.models import SessionLocal
            from app.models.agent_reflection import AgentReflection
            with SessionLocal() as db:
                rows = db.query(AgentReflection).filter(
                    AgentReflection.user_id == self.user_id,
                ).order_by(AgentReflection.created_at.asc()).all()
            if rows:
                self.global_entries = [ReflectionEntry.from_dict(row.entry_data) for row in rows]
                self.entries = [
                    ReflectionEntry.from_dict(row.entry_data)
                    for row in rows
                    if row.conversation_id == self.conversation_id
                ]
                return
        except Exception as e:
            logger.warning("Failed to load reflections from MySQL: %s", e)

        if self.reflections_file.exists():
            try:
                with open(self.reflections_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self.entries = [ReflectionEntry.from_dict(e) for e in raw]
            except Exception as e:
                logger.warning(f"Failed to load reflections: {e}")
                self.entries = []
        if self.global_reflections_file.exists():
            try:
                with open(self.global_reflections_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self.global_entries = [ReflectionEntry.from_dict(e) for e in raw]
            except Exception as e:
                logger.warning(f"Failed to load global reflections: {e}")
                self.global_entries = []
        if not self.global_entries:
            self.global_entries = self._load_legacy_user_reflections()

    def _load_legacy_user_reflections(self) -> List[ReflectionEntry]:
        """Aggregate old per-conversation reflection files into user-level memory."""
        entries: List[ReflectionEntry] = []
        seen = set()
        try:
            for path in self.user_dir.glob("*/reflections.json"):
                if path == self.global_reflections_file:
                    continue
                try:
                    raw = json.loads(path.read_text(encoding="utf-8") or "[]")
                except Exception:
                    continue
                for item in raw:
                    try:
                        entry = ReflectionEntry.from_dict(item)
                    except Exception:
                        continue
                    if entry.id in seen:
                        continue
                    seen.add(entry.id)
                    entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to aggregate legacy reflections: {e}")
        return entries

    def _persist_entry(self, entry: ReflectionEntry) -> None:
        try:
            from app.models import SessionLocal
            from app.models.agent_reflection import AgentReflection
            with SessionLocal() as db:
                row = db.get(AgentReflection, entry.id)
                if row is None:
                    row = AgentReflection(
                        entry_id=entry.id,
                        user_id=self.user_id,
                        conversation_id=self.conversation_id,
                        entry_data={},
                    )
                    db.add(row)
                row.entry_data = entry.to_dict()
                db.commit()
        except Exception as e:
            logger.error(f"Failed to save reflection: {e}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenizer for Chinese + English.

        Mirrors the tokenizer in rag_service.py for consistency:
        - English words / numbers kept as whole tokens
        - Chinese split into 2-character n-grams (with 1-char overlap)
        """
        text = text.lower()
        tokens: List[str] = []

        # English / alphanumeric tokens
        eng_pattern = re.compile(r"[a-z0-9]+")
        for m in eng_pattern.finditer(text):
            tokens.append(m.group())

        # Chinese 2-gram tokens (with 1-char overlap)
        cn_pattern = re.compile(r"[\u4e00-\u9fff]+")
        for m in cn_pattern.finditer(text):
            chars = m.group()
            for i in range(len(chars)):
                tokens.append(chars[i])
                if i + 2 <= len(chars):
                    tokens.append(chars[i : i + 2])

        return tokens

    def add_reflection(self, entry: ReflectionEntry) -> None:
        """Append a reflection entry and persist immediately."""
        self.entries.append(entry)
        if not any(e.id == entry.id for e in self.global_entries):
            self.global_entries.append(entry)
        self._persist_entry(entry)

    def search_relevant(self, query: str, top_k: int = 3) -> List[ReflectionEntry]:
        """Find the most relevant reflections for a query using TF-IDF."""
        entries = self._all_entries()
        if not entries or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Tokenize all entries' searchable text
        all_tokens = [self._tokenize(e.searchable_text()) for e in entries]

        # Document frequency
        df = Counter()
        for tokens in all_tokens:
            for token in set(tokens):
                df[token] += 1

        n_docs = len(entries)

        # IDF
        idf = {}
        for token, freq in df.items():
            idf[token] = math.log((n_docs + 1) / (freq + 1)) + 1

        # Score each entry
        scores = []
        for tokens in all_tokens:
            if not tokens:
                scores.append(0.0)
                continue
            tf = Counter(tokens)
            chunk_len = len(tokens)
            score = 0.0
            for q_token in query_tokens:
                if q_token in tf:
                    tf_val = tf[q_token] / chunk_len
                    score += tf_val * idf.get(q_token, 1.0)
            scores.append(score)

        # Rank descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in ranked[:top_k]:
            if score > 0:
                results.append(entries[idx])
        return results

    def _all_entries(self) -> List[ReflectionEntry]:
        """Current conversation entries first, then user-global entries without duplicates."""
        merged: List[ReflectionEntry] = []
        seen = set()
        for entry in list(self.entries) + list(reversed(self.global_entries)):
            if entry.id in seen:
                continue
            seen.add(entry.id)
            merged.append(entry)
        return merged

    def search_strategies(self, query: str, top_k: int = 3) -> List[str]:
        """Search for strategy hints relevant to the query.
        
        Returns list of strategy strings (most relevant first).
        Only returns entries that have a non-empty strategy_hint.
        """
        relevant = self.search_relevant(query, top_k=top_k * 2)
        strategies = []
        for e in relevant:
            if e.strategy_hint and e.strategy_hint.strip():
                strategies.append(e.strategy_hint.strip())
                if len(strategies) >= top_k:
                    break
        return strategies

    def get_recent(self, n: int = 5) -> List[ReflectionEntry]:
        """Return the *n* most recent reflections (newest first)."""
        return list(reversed(self.entries[-n:])) if self.entries else []

    def get_all(self) -> List[ReflectionEntry]:
        """Return all reflections in chronological order."""
        return self._all_entries()

    def clear(self) -> None:
        """Remove all reflections for this conversation."""
        removed = {entry.id for entry in self.entries}
        from app.models import SessionLocal
        from app.models.agent_reflection import AgentReflection
        with SessionLocal() as db:
            db.query(AgentReflection).filter(
                AgentReflection.user_id == self.user_id,
                AgentReflection.conversation_id == self.conversation_id,
            ).delete(synchronize_session=False)
            db.commit()
        self.entries = []
        self.global_entries = [entry for entry in self.global_entries if entry.id not in removed]


# Module-level cache: (user_hex, conv_dir_name) -> ReflectionStore
_store_cache: Dict[str, ReflectionStore] = {}


def get_reflection_store(user_id: bytes, conversation_id: str) -> ReflectionStore:
    """Get or create a ReflectionStore for a user + conversation."""
    import binascii

    user_hex = binascii.hexlify(user_id).decode("ascii") if user_id else "anonymous"
    conv_dir_name = conversation_id[:16]
    cache_key = f"{user_hex}:{conv_dir_name}"
    if cache_key not in _store_cache:
        _store_cache[cache_key] = ReflectionStore(user_id or b"anonymous", conversation_id)
    return _store_cache[cache_key]
