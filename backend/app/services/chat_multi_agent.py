# -*- coding: utf-8 -*-
"""
Conversation-level multi-agent orchestration.

The existing AutonomousAgent remains the answer engine. This module adds a
small diagnosis/retrieval/rule/judge layer around it and emits JSON-serializable
events that the current Steps UI can render without a frontend rewrite.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List

from app.services.rag_service import format_retrieval_context, get_kb


TEXT = {
    "fallback_source": "\u53c2\u8003\u8d44\u6599",
    "default_learner": "\u6682\u65e0\u53ef\u7528\u7528\u6237\u753b\u50cf\uff0c\u6309\u901a\u7528\u5b66\u4e60\u8005\u5904\u7406\u3002",
    "evidence_rule": "\u8d44\u6599\u68c0\u7d22",
    "explain_rule": "\u89e3\u91ca\u4efb\u52a1\u7b56\u7565",
    "source_rule": "\u6765\u6e90\u53ef\u89c1\u6027",
    "evidence_found": "\u68c0\u7d22\u5230 {count} \u6761\u53ef\u53c2\u8003\u8d44\u6599\u3002",
    "evidence_missing": "\u6ca1\u6709\u627e\u5230\u76f4\u63a5\u76f8\u5173\u8d44\u6599\uff0c\u56de\u7b54\u9700\u6807\u660e\u4e0d\u786e\u5b9a\u6027\u3002",
    "evidence_suggestion": "\u4f18\u5148\u5f15\u7528\u76f8\u5173\u8d44\u6599\u7247\u6bb5\u3002",
    "missing_suggestion": "\u907f\u514d\u628a\u672a\u68c0\u7d22\u5230\u7684\u5185\u5bb9\u8bf4\u6210\u6765\u81ea\u8d44\u6599\u5e93\u3002",
    "direct_explain": "\u89e3\u91ca\u578b\u95ee\u9898\u4f7f\u7528\u76f4\u63a5\u8bb2\u89e3\u7b56\u7565\u3002",
    "tool_allowed": "\u672c\u8f6e\u5141\u8bb8\u5de5\u5177\u4e0e\u8d44\u6599\u8f85\u52a9\u3002",
    "source_ready": "\u5df2\u751f\u6210\u53ef\u5c55\u793a\u7ed9\u524d\u7aef\u7684\u8bc1\u636e\u6765\u6e90\u7ed3\u6784\u3002",
    "diagnosis_agent": "\u5b66\u60c5\u8bca\u65ad",
    "retrieval_agent": "\u8bc1\u636e\u68c0\u7d22",
    "rules_agent": "\u89c4\u5219\u68c0\u67e5",
    "judge_agent": "\u88c1\u51b3",
    "diagnosis_content": "\u8bc6\u522b\u4efb\u52a1\u610f\u56fe\uff1a{intent}\uff0c\u6574\u7406\u7528\u6237\u753b\u50cf\u4e0e\u76ee\u6807\u3002",
    "judge_with_evidence": "\u8f93\u51fa\u5f53\u524d\u7b54\u6848\uff0c\u5e76\u5728\u524d\u7aef\u5c55\u793a\u8bc1\u636e\u6765\u6e90\u3002",
    "judge_without_evidence": "\u8f93\u51fa\u5f53\u524d\u7b54\u6848\uff1b\u672c\u8f6e\u65e0\u76f4\u63a5\u8d44\u6599\u6765\u6e90\u3002",
}

LEARNING_KEYS = (
    "\u5b66\u4e60", "\u8ba1\u5212", "\u77e5\u8bc6\u70b9",
    "\u8bfe\u7a0b", "\u7ec3\u4e60", "\u8bb2\u89e3",
)
CODING_KEYS = (
    "\u4ee3\u7801", "python", "java", "c\u8bed\u8a00", "c \u8bed\u8a00",
    "\u8fd0\u884c", "\u5b9e\u73b0",
)
EXPLANATION_KEYS = (
    "\u4e3a\u4ec0\u4e48", "\u89e3\u91ca", "\u539f\u7406",
    "\u7528\u4f8b\u5b50", "\u4e3e\u4f8b",
)
KNOWLEDGE_KEYS = (
    "\u8d44\u6599", "\u77e5\u8bc6\u5e93", "\u6839\u636e",
    "\u6765\u6e90", "\u5b66\u4e60", "\u8bfe\u7a0b", "\u8ba1\u5212",
)


@dataclass
class EvidenceRef:
    index: int
    title: str
    doc_id: str
    chunk_id: int
    score: float
    snippet: str
    category: str = ""


@dataclass
class RuleHit:
    rule_id: str
    name: str
    passed: bool
    severity: str
    message: str
    suggestion: str = ""


def _trace_id(user_id: bytes, conversation_id: str, user_input: str) -> str:
    raw = b"|".join([
        user_id or b"anonymous",
        (conversation_id or "").encode("utf-8", errors="ignore"),
        (user_input or "").encode("utf-8", errors="ignore"),
        datetime.utcnow().isoformat(timespec="seconds").encode("ascii"),
    ])
    return hashlib.sha1(raw).hexdigest()[:16]


def _snippet(text: str, limit: int = 220) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _compact_evidence(results: List[Dict[str, Any]]) -> List[EvidenceRef]:
    refs: List[EvidenceRef] = []
    for idx, item in enumerate(results or [], start=1):
        meta = item.get("metadata") or {}
        title = meta.get("title") or meta.get("source") or item.get("doc_id") or TEXT["fallback_source"]
        refs.append(EvidenceRef(
            index=idx,
            title=str(title),
            doc_id=str(item.get("doc_id") or ""),
            chunk_id=int(item.get("chunk_id") or 0),
            score=float(item.get("score") or 0.0),
            snippet=_snippet(item.get("content") or ""),
            category=str(meta.get("category") or ""),
        ))
    return refs


def _diagnose(user_input: str, profile_context: str = "") -> Dict[str, Any]:
    text = (user_input or "").strip()
    lower = text.lower()
    intent = "general"
    if any(key in text for key in LEARNING_KEYS):
        intent = "learning"
    if any(key in lower for key in CODING_KEYS):
        intent = "coding"
    if any(key in text for key in EXPLANATION_KEYS):
        intent = "explanation"

    return {
        "intent": intent,
        "learner_state": profile_context[:600] if profile_context else TEXT["default_learner"],
        "task_goal": text[:300],
        "risk_level": "medium" if intent in {"coding", "learning"} else "low",
    }


def _evaluate_rules(
    user_input: str,
    evidence_refs: List[EvidenceRef],
    direct_answer_mode: bool,
) -> List[RuleHit]:
    text = (user_input or "").strip()
    looks_knowledge = any(key in text for key in KNOWLEDGE_KEYS)
    looks_explanation = any(key in text for key in EXPLANATION_KEYS)

    return [
        RuleHit(
            rule_id="evidence_track",
            name=TEXT["evidence_rule"],
            passed=bool(evidence_refs) or not looks_knowledge,
            severity="major" if looks_knowledge else "minor",
            message=(
                TEXT["evidence_found"].format(count=len(evidence_refs))
                if evidence_refs else TEXT["evidence_missing"]
            ),
            suggestion=TEXT["evidence_suggestion"] if evidence_refs else TEXT["missing_suggestion"],
        ),
        RuleHit(
            rule_id="direct_explanation",
            name=TEXT["explain_rule"],
            passed=(direct_answer_mode if looks_explanation else True),
            severity="minor",
            message=TEXT["direct_explain"] if direct_answer_mode else TEXT["tool_allowed"],
        ),
        RuleHit(
            rule_id="source_visibility",
            name=TEXT["source_rule"],
            passed=True,
            severity="major",
            message=TEXT["source_ready"],
        ),
    ]


def _context_text(
    trace_id: str,
    diagnosis: Dict[str, Any],
    evidence_refs: List[EvidenceRef],
    rule_hits: List[RuleHit],
    retrieval_context: str,
) -> str:
    rules = "\n".join(
        f"- {hit.rule_id}: {'PASS' if hit.passed else 'FAIL'} | {hit.message}"
        for hit in rule_hits
    )
    refs = "\n".join(
        f"- Source {ref.index}: {ref.title} | doc_id={ref.doc_id} | chunk={ref.chunk_id} | score={ref.score:.3f}"
        for ref in evidence_refs
    ) or "- No direct evidence found."

    return (
        "[Agent Context]\n"
        f"trace_id: {trace_id}\n"
        f"diagnosis: {diagnosis}\n"
        "rule_hits:\n"
        f"{rules}\n"
        "visible_evidence_refs:\n"
        f"{refs}\n\n"
        f"{retrieval_context}\n"
        "[End Agent Context]\n"
        "When sources are relevant, ground the answer in them. "
        "If sources are weak or absent, say so plainly."
    )


def prepare_chat_multi_agent_context(
    *,
    user_id: bytes,
    conversation_id: str,
    user_input: str,
    profile_context: str = "",
    direct_answer_mode: bool = False,
    top_k: int = 5,
) -> Dict[str, Any]:
    trace_id = _trace_id(user_id, conversation_id, user_input)
    diagnosis = _diagnose(user_input, profile_context)

    retrieval: List[Dict[str, Any]] = []
    try:
        kb = get_kb(user_id)
        if kb.list_documents():
            retrieval = kb.search(user_input, top_k=top_k)
    except Exception:
        retrieval = []

    evidence_refs = _compact_evidence(retrieval)
    rule_hits = _evaluate_rules(user_input, evidence_refs, direct_answer_mode)
    retrieval_context = format_retrieval_context(retrieval, max_chars=9000) if retrieval else ""
    context = _context_text(trace_id, diagnosis, evidence_refs, rule_hits, retrieval_context)
    evidence_payload = [asdict(ref) for ref in evidence_refs]
    rule_payload = [asdict(hit) for hit in rule_hits]

    return {
        "trace_id": trace_id,
        "diagnosis": diagnosis,
        "evidence_refs": evidence_payload,
        "rule_hits": rule_payload,
        "context": context,
        "events": [
            {
                "type": "thinking",
                "data": {
                    "step": 0,
                    "agent": "diagnosis",
                    "agent_name": TEXT["diagnosis_agent"],
                    "intent": diagnosis["intent"],
                    "content": TEXT["diagnosis_content"].format(intent=diagnosis["intent"]),
                },
            },
            {
                "type": "observation",
                "data": {
                    "step": 0,
                    "agent": "retrieval",
                    "agent_name": TEXT["retrieval_agent"],
                    "success": True,
                    "formatted": TEXT["evidence_found"].format(count=len(evidence_refs)),
                    "evidence_refs": evidence_payload,
                },
            },
            {
                "type": "observation",
                "data": {
                    "step": 0,
                    "agent": "rules",
                    "agent_name": TEXT["rules_agent"],
                    "success": all(hit.passed or hit.severity != "critical" for hit in rule_hits),
                    "formatted": "\n".join(hit.message for hit in rule_hits),
                    "rule_hits": rule_payload,
                },
            },
        ],
    }


def judge_chat_answer(answer: str, context: Dict[str, Any]) -> Dict[str, Any]:
    evidence_refs = context.get("evidence_refs") or []
    rule_hits = context.get("rule_hits") or []
    answer_text = answer or ""

    cited = any(
        ref.get("title") and ref.get("title") in answer_text
        for ref in evidence_refs
    ) or any(token in answer_text for token in ("\u6765\u6e90", "\u53c2\u8003", "\u8d44\u6599"))
    failed_major = [
        hit for hit in rule_hits
        if not hit.get("passed") and hit.get("severity") in {"major", "critical"}
    ]

    risk_level = "low"
    if failed_major:
        risk_level = "medium"
    if evidence_refs and not cited:
        risk_level = "medium"
    if not answer_text.strip():
        risk_level = "high"

    confidence = "high" if evidence_refs and risk_level == "low" else "medium"
    if risk_level == "high":
        confidence = "low"

    return {
        "agent": "judge",
        "agent_name": TEXT["judge_agent"],
        "risk_level": risk_level,
        "confidence": confidence,
        "proposed_action": TEXT["judge_with_evidence"] if evidence_refs else TEXT["judge_without_evidence"],
        "cited_sources": bool(cited),
        "trace_id": context.get("trace_id"),
    }
