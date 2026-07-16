# -*- coding: utf-8 -*-
"""LangGraph-based multi-agent orchestration for chat and debugging APIs."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.services.rag_service import format_retrieval_context, get_kb
from app.services.knowledge_scope import SYSTEM_KB_USER_ID, readable_owner_ids
from app.tools.learning.knowledge_search_tool import KnowledgeSearchTool


AgentId = Literal["diagnosis", "retrieval", "rules", "human_gate", "judge", "full"]


TEXT = {
    "fallback_source": "\u53c2\u8003\u8d44\u6599",
    "default_learner": "\u6682\u65e0\u53ef\u7528\u7528\u6237\u753b\u50cf\uff0c\u6309\u901a\u7528\u5b66\u4e60\u8005\u5904\u7406\u3002",
    "diagnosis_agent": "学情诊断 Agent",
    "retrieval_agent": "检索 Agent",
    "rules_agent": "规则校验",
    "human_agent": "人工确认",
    "judge_agent": "裁判 Agent",
    "evidence_rule": "\u8d44\u6599\u68c0\u7d22",
    "explain_rule": "\u89e3\u91ca\u4efb\u52a1\u7b56\u7565",
    "source_rule": "\u6765\u6e90\u53ef\u89c1\u6027",
    "human_rule": "\u4eba\u5728\u56de\u8def\u7b56\u7565",
    "evidence_found": "\u68c0\u7d22\u5230 {count} \u6761\u53ef\u53c2\u8003\u8d44\u6599\u3002",
    "evidence_missing": "\u6ca1\u6709\u627e\u5230\u76f4\u63a5\u76f8\u5173\u8d44\u6599\uff0c\u56de\u7b54\u9700\u6807\u660e\u4e0d\u786e\u5b9a\u6027\u3002",
    "human_required": "这一步资料不足或风险较高，需要你的确认后才能继续。",
    "human_not_required": "本轮无需你的确认。",
    "human_approved": "你已确认继续。",
    "source_ready": "参考资料已整理完毕。",
    "source_absent": "当前没有可展示的参考来源。",
    "live_evidence_pending": "\u5df2\u8df3\u8fc7\u975e\u5b9e\u65f6\u8d44\u6599\uff0c\u7b49\u5f85\u8054\u7f51\u5de5\u5177\u8fd4\u56de\u53ef\u6838\u9a8c\u6765\u6e90\u3002",
    "direct_explain": "\u89e3\u91ca\u578b\u95ee\u9898\u4f7f\u7528\u76f4\u63a5\u8bb2\u89e3\u7b56\u7565\u3002",
    "tool_allowed": "\u672c\u8f6e\u5141\u8bb8\u5de5\u5177\u4e0e\u8d44\u6599\u8f85\u52a9\u3002",
    "judge_with_evidence": "回答已完成核对，并附有参考来源。",
    "judge_without_evidence": "回答已完成核对，本轮未使用外部参考资料。",
    "source_not_needed": "本轮无需外部参考资料。",
    "direct_response": "\u5f53\u524d\u4efb\u52a1\u91c7\u7528\u76f4\u63a5\u56de\u7b54\u7b56\u7565\u3002",
    "judge_with_warning": "\u5df2\u751f\u6210\u56de\u7b54\uff0c\u4f46\u5b58\u5728\u5ba1\u6838\u63d0\u793a\uff0c\u5efa\u8bae\u8c28\u614e\u91c7\u7528\u3002",
}

LEARNING_KEYS = ("\u5b66\u4e60", "\u8ba1\u5212", "\u77e5\u8bc6\u70b9", "\u8bfe\u7a0b", "\u7ec3\u4e60", "\u8bb2\u89e3")
CODING_KEYS = ("\u4ee3\u7801", "python", "java", "c\u8bed\u8a00", "c \u8bed\u8a00", "\u8fd0\u884c", "\u5b9e\u73b0")
EXPLANATION_KEYS = ("\u4e3a\u4ec0\u4e48", "\u89e3\u91ca", "\u539f\u7406", "\u7528\u4f8b\u5b50", "\u4e3e\u4f8b")
KNOWLEDGE_KEYS = ("\u8d44\u6599", "\u77e5\u8bc6\u5e93", "\u6839\u636e", "\u6765\u6e90", "\u5b66\u4e60", "\u8bfe\u7a0b", "\u8ba1\u5212")
CAPABILITY_KEYS = (
    "你能帮我", "你可以帮我", "你会做什么", "你能做什么", "你有什么能力",
    "你可以做什么", "怎么使用你", "如何使用你", "介绍一下你自己",
)
LIVE_INFO_KEYS = (
    "最新", "实时", "天气", "气温", "降雨", "空气质量", "汇率", "股票", "股价",
    "新闻", "热搜", "比分", "航班", "价格", "官网", "股市", "大盘", "行情", "当前时间", "现在几点",
    "今天几号", "星期几",
)
RESEARCH_KEYS = (
    "深度调研", "论文检索", "文献检索", "研究综述", "相关论文", "学术论文",
)
SMALLTALK_TEXTS = {"你好", "嗨", "hi", "hello", "谢谢", "感谢", "再见", "晚安"}
INTENT_LABELS = {
    "capability": "能力咨询",
    "live_info": "实时查询",
    "research": "深度调研",
    "smalltalk": "日常对话",
    "coding": "代码任务",
    "explanation": "概念讲解",
    "learning": "学习任务",
    "general": "普通问答",
}
COURSE_QUERY_NOISE = (
    "请问", "请帮我", "帮我", "我想学习", "我想了解", "我该如何",
    "用例子解释", "解释", "为什么", "如何", "怎么", "怎样", "是什么",
    "方面的知识", "相关知识", "入门", "核心概念", "实践", "讲一讲", "说一说",
)

STATIC_KNOWLEDGE_TOPICS = (
    "python", "java", "javascript", "typescript", "node.js", "nodejs", "go ", "golang",
    "c语言", "c++", "redis", "mysql", "sql", "docker", "linux", "git", "http", "api",
    "numpy", "pandas", "pytorch", "tensorflow", "机器学习", "深度学习", "算法", "排序",
    "llm", "大模型", "agent", "智能体", "rag", "向量检索", "langchain", "langgraph",
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
    source_url: str = ""


@dataclass
class RuleHit:
    rule_id: str
    name: str
    passed: bool
    severity: str
    message: str
    suggestion: str = ""


class AgentState(TypedDict, total=False):
    user_id_hex: str
    user_id_bytes: bytes
    conversation_id: str
    user_input: str
    profile_context: str
    direct_answer_mode: bool
    top_k: int
    trace_id: str
    answer: str
    human_approved: bool
    human_feedback: str
    enable_human_interrupt: bool
    diagnosis: Dict[str, Any]
    task_policy: Dict[str, Any]
    retrieval: List[Dict[str, Any]]
    evidence_refs: List[Dict[str, Any]]
    rule_hits: List[Dict[str, Any]]
    retrieval_context: str
    context: str
    human_review_required: bool
    human_status: str
    judge: Dict[str, Any]
    review: Dict[str, Any]
    events: List[Dict[str, Any]]


def _trace_id(user_id: bytes, conversation_id: str, user_input: str) -> str:
    raw = b"|".join([
        user_id or b"anonymous",
        (conversation_id or "").encode("utf-8", errors="ignore"),
        (user_input or "").encode("utf-8", errors="ignore"),
        datetime.now(timezone.utc).isoformat(timespec="seconds").encode("ascii"),
    ])
    return hashlib.sha1(raw).hexdigest()[:16]


def _event(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": kind, "data": data}


def _append_event(state: AgentState, kind: str, data: Dict[str, Any]) -> None:
    state.setdefault("events", []).append(_event(kind, data))


def _snippet(text: str, limit: int = 220) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _normalize_url(value: Any) -> str:
    url = str(value or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


def _course_subject_terms(query: str) -> List[str]:
    """Extract subject words so generic phrasing cannot match random courses."""
    cleaned = (query or "").lower()
    for phrase in COURSE_QUERY_NOISE:
        cleaned = cleaned.replace(phrase.lower(), " ")
    terms = re.findall(r"[a-z][a-z0-9+#.\-]{1,}|[\u4e00-\u9fff]{2,}", cleaned)
    return [term for term in terms if term not in {"一天", "一个", "一周", "知识"}]


def _course_matches_query(query: str, course: Dict[str, Any], page: Dict[str, Any]) -> bool:
    terms = _course_subject_terms(query)
    if not terms:
        return False
    haystack = " ".join((
        str(page.get("title") or ""),
        str(page.get("summary") or ""),
        str(course.get("course_name") or ""),
    )).lower()
    return any(term in haystack for term in terms)


def _retrieval_query(user_input: str, intent: str) -> str:
    """Remove conversational intent words while preserving the subject."""
    query = (user_input or "").strip()
    for phrase in (
        "请问", "请帮我", "帮我", "我想学习", "我想了解", "我该如何",
        "方面的知识", "相关知识", "制定一周", "制定一个", "学习计划",
    ):
        query = query.replace(phrase, " ")
    query = re.sub(r"\s+", " ", query).strip(" ，。！？?")
    if intent == "learning":
        query = f"{query} 入门 核心概念 实践".strip()
    return query or (user_input or "")


def _should_use_system_courses(user_input: str) -> bool:
    """Use the bundled tutorial catalog only when the user explicitly asks for it."""
    text = (user_input or "").lower()
    return any(marker in text for marker in (
        "预置课程库", "系统课程库", "内置课程库", "教程库", "课程资料库",
        "从课程库", "在课程库", "根据课程库", "菜鸟教程",
    ))


def _should_use_public_knowledge(user_input: str) -> bool:
    """Use shared static material only when the question has a supported technical subject."""
    text = (user_input or "").lower()
    return _should_use_system_courses(text) or any(topic in text for topic in STATIC_KNOWLEDGE_TOPICS)


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
            source_url=_normalize_url(meta.get("url") or meta.get("source_url") or meta.get("source") or meta.get("link")),
        ))
    return refs


def _diagnose_text(user_input: str, profile_context: str = "") -> Dict[str, Any]:
    text = (user_input or "").strip()
    lower = text.lower()
    intent = "general"
    code_action = any(marker in text for marker in (
        "写代码", "写一个程序", "实现代码", "运行代码", "执行代码", "调试", "报错", "修复代码",
    )) or ("运行" in text and any(key in lower for key in CODING_KEYS))
    normalized = re.sub(r"[\s，。！!？?]+", "", lower)
    if any(key in text for key in LIVE_INFO_KEYS) or "http://" in lower or "https://" in lower:
        intent = "live_info"
    elif any(key in text for key in RESEARCH_KEYS):
        intent = "research"
    elif any(key in text for key in CAPABILITY_KEYS):
        intent = "capability"
    elif normalized in SMALLTALK_TEXTS:
        intent = "smalltalk"
    elif any(key in text for key in EXPLANATION_KEYS):
        intent = "explanation"
    elif any(key in text for key in LEARNING_KEYS):
        intent = "learning"
    elif code_action:
        intent = "coding"
    return {
        "intent": intent,
        "learner_state": profile_context[:600] if profile_context else TEXT["default_learner"],
        "task_goal": text[:300],
        "risk_level": "medium" if intent in {"coding", "learning", "research"} else "low",
    }


def build_task_policy(user_input: str) -> Dict[str, Any]:
    """Build generic ownership and side-effect limits for one request."""
    text = (user_input or "").strip()
    allow_plan_write = "计划" in text and any(
        marker in text for marker in ("保存", "创建", "新建", "添加", "加入", "写入")
    )
    allow_file_write = (
        "文件" in text
        and any(marker in text for marker in ("保存", "生成", "创建", "写入", "写一个"))
    ) or "落盘" in text
    diagnosis = _diagnose_text(text)
    requires_execution = diagnosis.get("intent") == "coding" or allow_plan_write or allow_file_write
    requires_live_search = diagnosis.get("intent") in {"live_info", "research"} or any(
        marker in text for marker in ("联网搜索", "上网查", "搜索网络")
    )
    # Profile and knowledge retrieval are owned by dedicated graph nodes.
    blocked_tools = ["learner_profile", "knowledge_search", "knowledge_graph", "skill_graph"]
    if not allow_plan_write:
        blocked_tools.append("goal_disassemble")
    if not allow_file_write:
        blocked_tools.append("file_write")
    return {
        "blocked_tools": blocked_tools,
        "explicit_write": allow_plan_write or allow_file_write,
        "allow_plan_write": allow_plan_write,
        "allow_file_write": allow_file_write,
        "requires_execution": requires_execution,
        "requires_live_search": requires_live_search,
        "owners": {
            "profile": "diagnosis",
            "retrieval": "retrieval",
            "generation": "generation",
            "review": "review",
            "decision": "judge",
        },
        "max_identical_tool_calls": 1,
    }


def _rule_hits(user_input: str, evidence_refs: List[Dict[str, Any]], direct_answer_mode: bool) -> List[RuleHit]:
    text = (user_input or "").strip()
    intent = _diagnose_text(text).get("intent")
    is_live = intent in {"live_info", "research"}
    source_not_needed = intent in {"capability", "smalltalk", "coding"}
    looks_knowledge = any(key in text for key in KNOWLEDGE_KEYS)
    looks_explanation = any(key in text for key in EXPLANATION_KEYS)
    high_risk = any(marker in text for marker in (
        "删除数据", "覆盖文件", "发送邮件", "发布", "支付", "转账", "修改数据库", "执行生产",
    ))
    human_needed = high_risk
    return [
        RuleHit(
            rule_id="evidence_track",
            name=TEXT["evidence_rule"],
            passed=bool(evidence_refs) or not looks_knowledge,
            severity="major" if looks_knowledge else "minor",
            message=(
                TEXT["evidence_found"].format(count=len(evidence_refs))
                if evidence_refs else (
                    TEXT["source_not_needed"] if source_not_needed
                    else (TEXT["live_evidence_pending"] if is_live else TEXT["evidence_missing"])
                )
            ),
        ),
        RuleHit(
            rule_id="direct_explanation",
            name=TEXT["explain_rule"],
            passed=(direct_answer_mode if looks_explanation else True),
            severity="minor",
            message=(
                TEXT["direct_response"] if source_not_needed and direct_answer_mode
                else (TEXT["direct_explain"] if direct_answer_mode else TEXT["tool_allowed"])
            ),
        ),
        RuleHit(
            rule_id="source_visibility",
            name=TEXT["source_rule"],
            passed=True,
            severity="major",
            message=TEXT["source_ready"] if evidence_refs else (
                TEXT["source_not_needed"] if source_not_needed
                else (TEXT["live_evidence_pending"] if is_live else TEXT["source_absent"])
            ),
        ),
        RuleHit(
            rule_id="human_review",
            name=TEXT["human_rule"],
            passed=not human_needed,
            severity="major" if human_needed else "minor",
            message=TEXT["human_required"] if human_needed else TEXT["human_not_required"],
        ),
    ]


def _context_text(state: AgentState) -> str:
    rule_hits = state.get("rule_hits") or []
    evidence_refs = state.get("evidence_refs") or []
    rules = "\n".join(
        f"- {hit.get('rule_id')}: {'PASS' if hit.get('passed') else 'FAIL'} | {hit.get('message')}"
        for hit in rule_hits
    )
    refs = "\n".join(
        f"- Source {ref.get('index')}: {ref.get('title')} | doc_id={ref.get('doc_id')} | chunk={ref.get('chunk_id')} | score={float(ref.get('score') or 0.0):.3f}"
        for ref in evidence_refs
    ) or "- No direct evidence found."
    return (
        "[LangGraph Agent Context]\n"
        f"trace_id: {state.get('trace_id')}\n"
        f"diagnosis: {state.get('diagnosis')}\n"
        f"task_policy: {state.get('task_policy')}\n"
        f"human_review_required: {state.get('human_review_required', False)}\n"
        "rule_hits:\n"
        f"{rules}\n"
        "visible_evidence_refs:\n"
        f"{refs}\n\n"
        f"{state.get('retrieval_context') or ''}\n"
        "[End LangGraph Agent Context]\n"
        "When sources are relevant, ground the answer in them. If sources are weak or absent, say so plainly."
    )


def diagnosis_node(state: AgentState) -> AgentState:
    diagnosis = _diagnose_text(state.get("user_input", ""), state.get("profile_context", ""))
    state["diagnosis"] = diagnosis
    state["task_policy"] = build_task_policy(state.get("user_input", ""))
    state.setdefault("trace_id", _trace_id(state.get("user_id_bytes", b""), state.get("conversation_id", ""), state.get("user_input", "")))
    intent = diagnosis["intent"]
    agent_name = TEXT["diagnosis_agent"] if intent == "learning" else "任务识别 Agent"
    _append_event(state, "thinking", {
        "step": 0,
        "agent": "diagnosis",
        "agent_name": agent_name,
        "intent": intent,
        "intent_label": INTENT_LABELS.get(intent, intent),
        "transition": f"先由{agent_name} 确认问题类型和目标，再决定后续处理路径。",
        "content": f"{agent_name} 已确认本轮为{INTENT_LABELS.get(intent, intent)}。",
    })
    return state


def retrieval_node(state: AgentState) -> AgentState:
    retrieval: List[Dict[str, Any]] = []
    diagnosis = state.get("diagnosis") or _diagnose_text(state.get("user_input", ""))
    retrieval_query = _retrieval_query(state.get("user_input", ""), diagnosis.get("intent", "general"))
    if diagnosis.get("intent") in {"coding", "capability", "live_info", "research", "smalltalk"}:
        state["retrieval"] = []
        state["evidence_refs"] = []
        state["retrieval_context"] = ""
        if diagnosis.get("intent") in {"live_info", "research"}:
            formatted = (
                "已跳过普通课程资料，交由互联网与论文来源检索。"
                if diagnosis.get("intent") == "research"
                else "已跳过非实时课程资料，交由互联网搜索处理。"
            )
            _append_event(state, "observation", {
                "step": 0,
                "agent": "retrieval",
                "agent_name": TEXT["retrieval_agent"],
                "success": True,
                "transition": "任务类型已经明确，接下来由检索 Agent 选择与时效要求匹配的资料来源。",
                "formatted": formatted,
                "evidence_refs": [],
            })
        return state
    try:
        owner_ids = readable_owner_ids(state.get("user_id_bytes", b""))
        seen_hits = set()
        for owner_id in owner_ids:
            if owner_id == SYSTEM_KB_USER_ID and not _should_use_public_knowledge(state.get("user_input", "")):
                continue
            kb = get_kb(owner_id)
            if not kb.list_documents():
                continue
            for item in kb.search(retrieval_query, top_k=int(state.get("top_k") or 5)):
                if float(item.get("score") or 0.0) < 0.2:
                    continue
                key = (item.get("doc_id"), item.get("chunk_id"))
                if key in seen_hits:
                    continue
                seen_hits.add(key)
                payload = dict(item)
                metadata = dict(payload.get("metadata") or {})
                if owner_id == SYSTEM_KB_USER_ID and not _normalize_url(
                    metadata.get("source_url") or metadata.get("canonical_url") or metadata.get("url")
                ):
                    continue
                metadata["knowledge_scope"] = "public" if owner_id == SYSTEM_KB_USER_ID else "private"
                payload["metadata"] = metadata
                retrieval.append(payload)
        retrieval.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        retrieval = retrieval[:int(state.get("top_k") or 5)]
    except Exception:
        retrieval = []
    if len(retrieval) < int(state.get("top_k") or 5) and _should_use_public_knowledge(state.get("user_input", "")):
        try:
            course_result = KnowledgeSearchTool().search_sync(
                retrieval_query,
                limit=int(state.get("top_k") or 5),
            )
            existing = {(str(item.get("doc_id")), int(item.get("chunk_id") or 0)) for item in retrieval}
            page_candidates = []
            for course_rank, course in enumerate(course_result.get("results") or []):
                for page_index, page in enumerate(course.get("pages") or []):
                    priority = int(page.get("priority") or 0)
                    if diagnosis.get("intent") == "learning" and priority < 0:
                        continue
                    page_candidates.append((
                        float(page.get("score") or course.get("score") or 0.0),
                        priority,
                        -course_rank,
                        -page_index,
                        course,
                        page,
                    ))
            page_candidates.sort(reverse=True, key=lambda item: item[:4])
            course_counts: Dict[str, int] = {}
            source_counts: Dict[str, int] = {}
            for raw_score, _, _, _, course, page in page_candidates:
                if raw_score < 8.0 or not _course_matches_query(retrieval_query, course, page):
                    continue
                course_id = str(course.get("course_id") or "unknown")
                if course_counts.get(course_id, 0) >= 3:
                    continue
                doc_id = f"course:{course_id}"
                page_key = str(page.get("slug") or page.get("title") or "")
                chunk_id = int(hashlib.sha1(page_key.encode("utf-8")).hexdigest()[:8], 16)
                if (doc_id, chunk_id) in existing:
                    continue
                summary = str(page.get("summary") or "")
                url_match = re.search(r"https?://[^\s)\]]+", summary)
                source_url = url_match.group(0) if url_match else ""
                source_domain = urlparse(source_url).netloc.lower().removeprefix("www.") or "course"
                domain_limit = 1 if source_domain.endswith("runoob.com") else 2
                if source_counts.get(source_domain, 0) >= domain_limit:
                    continue
                retrieval.append({
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "content": summary,
                    "score": round(raw_score / (raw_score + 10.0), 6),
                    "metadata": {
                        "title": page.get("title") or course.get("course_name"),
                        "category": course.get("course_name") or "",
                        "source_url": source_url,
                        "course_id": course.get("course_id") or "",
                        "slug": page.get("slug") or "",
                    },
                })
                existing.add((doc_id, chunk_id))
                course_counts[course_id] = course_counts.get(course_id, 0) + 1
                source_counts[source_domain] = source_counts.get(source_domain, 0) + 1
                if len(retrieval) >= int(state.get("top_k") or 5):
                    break
        except Exception:
            # User-uploaded RAG results remain usable if the project course
            # index is unavailable or malformed.
            pass
    evidence_refs = [asdict(ref) for ref in _compact_evidence(retrieval)]
    state["retrieval"] = retrieval
    state["evidence_refs"] = evidence_refs
    state["retrieval_context"] = format_retrieval_context(retrieval, max_chars=9000) if retrieval else ""
    _append_event(state, "observation", {
        "step": 0,
        "agent": "retrieval",
        "agent_name": TEXT["retrieval_agent"],
        "success": True,
        "transition": "任务范围已经明确，接下来由检索 Agent 查找与问题直接相关的资料。",
        "formatted": (
            f"检索 Agent 筛选出 {len(evidence_refs)} 条可用于回答的资料。"
            if evidence_refs else "检索 Agent 未找到达到相关度要求的资料，将避免引用弱相关内容。"
        ),
        "evidence_refs": evidence_refs,
    })
    return state


def rules_node(state: AgentState) -> AgentState:
    hits = _rule_hits(
        state.get("user_input", ""),
        state.get("evidence_refs") or [],
        bool(state.get("direct_answer_mode")),
    )
    payload = [asdict(hit) for hit in hits]
    state["rule_hits"] = payload
    state["human_review_required"] = any(hit.rule_id == "human_review" and not hit.passed for hit in hits)
    state["context"] = _context_text(state)
    intent = (state.get("diagnosis") or {}).get("intent")
    if intent not in {"capability", "smalltalk"}:
        _append_event(state, "observation", {
            "step": 0,
            "agent": "rules",
            "agent_name": TEXT["rules_agent"],
            "success": all(hit.passed for hit in hits),
            "transition": "资料策略已经确定，接下来检查回答边界、来源要求和是否需要你的确认。",
            "formatted": "\n".join(hit.message for hit in hits),
            "rule_hits": payload,
        })
    return state


def human_gate_node(state: AgentState) -> AgentState:
    required = bool(state.get("human_review_required"))
    approved = bool(state.get("human_approved"))
    if required and not approved:
        if state.get("enable_human_interrupt"):
            decision = interrupt({
                "type": "human_review",
                "trace_id": state.get("trace_id"),
                "title": "需要你的确认",
                "message": TEXT["human_required"],
                "risk_level": "high",
                "action": state.get("user_input", "")[:240],
            })
            approved = bool((decision or {}).get("approved"))
            state["human_approved"] = approved
            state["human_feedback"] = str((decision or {}).get("feedback") or "")
            status = "approved" if approved else "rejected"
            content = TEXT["human_approved"] if approved else "用户已取消本次执行。"
        else:
            status = "needs_human"
            content = TEXT["human_required"]
    elif required and approved:
        status = "approved"
        content = TEXT["human_approved"]
    else:
        status = "not_required"
        content = TEXT["human_not_required"]
    state["human_status"] = status
    if required:
        _append_event(state, "reflection", {
            "step": 0,
            "agent": "human_gate",
            "agent_name": TEXT["human_agent"],
            "transition": "规则检查发现这一步可能产生风险，接下来需要你决定是否继续。",
            "overall": "HUMAN_REQUIRED" if status == "needs_human" else ("PASS" if status == "approved" else "CANCELLED"),
            "content": content,
            "requires_human": status == "needs_human",
            "approved": approved,
            "feedback": state.get("human_feedback", ""),
            "trace_id": state.get("trace_id"),
        })
    return state


def judge_node(state: AgentState) -> AgentState:
    answer_text = state.get("answer") or ""
    evidence_refs = state.get("evidence_refs") or []
    rule_hits = state.get("rule_hits") or []
    # Evidence references are rendered next to the answer by the chat UI.
    cited = bool(evidence_refs)
    failed_major = [
        hit for hit in rule_hits
        if not hit.get("passed") and hit.get("severity") in {"major", "critical"}
    ]
    requires_live_search = bool((state.get("task_policy") or {}).get("requires_live_search"))
    review = state.get("review") or {}
    review_failed = review.get("overall") == "FAIL"
    review_scores = review.get("scores") or {}
    risk_level = "low"
    if failed_major or (evidence_refs and not cited) or state.get("human_status") == "needs_human":
        risk_level = "medium"
    invalid_answer = (
        not answer_text.strip()
        or answer_text.startswith("抱歉，本次没有生成有效回答")
        or answer_text.startswith("模型服务暂时不可用")
        or answer_text.startswith("Error:")
        or answer_text.strip() == "task incomplete"
        or any(marker in answer_text for marker in ("DSML", "tool_calls", "<invoke", "<｜tool", "<|tool"))
    )
    if invalid_answer:
        risk_level = "high"
    if requires_live_search and not evidence_refs:
        risk_level = "high"
    if review_failed and risk_level != "high":
        risk_level = "medium" if risk_level == "low" else risk_level
    factual_score = review_scores.get("factual_grounding")
    if requires_live_search and factual_score is not None and float(factual_score) < 0.8:
        risk_level = "high"
    confidence = "high" if evidence_refs and risk_level == "low" else "medium"
    if risk_level == "high":
        confidence = "low"
    judge = {
        "agent": "judge",
        "agent_name": TEXT["judge_agent"],
        "risk_level": risk_level,
        "confidence": confidence,
        "proposed_action": (
            "本轮未生成可用回答，请重新执行。" if invalid_answer
            else (TEXT["judge_with_warning"] if review_failed
            else (TEXT["judge_with_evidence"] if evidence_refs else TEXT["judge_without_evidence"])
            )
        ),
        "cited_sources": bool(cited),
        "trace_id": state.get("trace_id"),
    }
    state["judge"] = judge
    _append_event(state, "reflection", {
        "step": 0,
        "agent": "judge",
        "agent_name": TEXT["judge_agent"],
        "transition": "回答已经生成并完成必要检查，最后由裁判 Agent 核对可信度和风险。",
        "overall": "PASS" if risk_level == "low" else ("CHECK" if risk_level == "medium" else "FAIL"),
        "content": judge["proposed_action"],
        "risk_level": risk_level,
        "confidence": confidence,
        "proposed_action": judge["proposed_action"],
        "cited_sources": judge["cited_sources"],
        "trace_id": state.get("trace_id"),
    })
    return state


def _build_pre_answer_graph():
    graph = StateGraph(AgentState)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("rules", rules_node)
    graph.add_node("human_gate", human_gate_node)
    graph.add_edge(START, "diagnosis")
    graph.add_edge("diagnosis", "retrieval")
    graph.add_edge("retrieval", "rules")
    graph.add_edge("rules", "human_gate")
    graph.add_edge("human_gate", END)
    return graph.compile(checkpointer=_CHECKPOINTER)


def _build_full_graph():
    graph = StateGraph(AgentState)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("rules", rules_node)
    graph.add_node("human_gate", human_gate_node)
    graph.add_node("judge", judge_node)
    graph.add_edge(START, "diagnosis")
    graph.add_edge("diagnosis", "retrieval")
    graph.add_edge("retrieval", "rules")
    graph.add_edge("rules", "human_gate")
    graph.add_edge("human_gate", "judge")
    graph.add_edge("judge", END)
    return graph.compile(checkpointer=_CHECKPOINTER)


_CHECKPOINTER = MemorySaver()
_PRE_ANSWER_GRAPH = None
_FULL_GRAPH = None


def get_pre_answer_graph():
    global _PRE_ANSWER_GRAPH
    if _PRE_ANSWER_GRAPH is None:
        _PRE_ANSWER_GRAPH = _build_pre_answer_graph()
    return _PRE_ANSWER_GRAPH


def get_full_graph():
    global _FULL_GRAPH
    if _FULL_GRAPH is None:
        _FULL_GRAPH = _build_full_graph()
    return _FULL_GRAPH


def make_initial_state(
    *,
    user_id: bytes,
    conversation_id: str,
    user_input: str,
    profile_context: str = "",
    direct_answer_mode: bool = False,
    answer: str = "",
    human_approved: bool = False,
    top_k: int = 5,
) -> AgentState:
    return {
        "user_id_bytes": user_id,
        "user_id_hex": user_id.hex() if user_id else "anonymous",
        "conversation_id": conversation_id,
        "user_input": user_input,
        "profile_context": profile_context,
        "direct_answer_mode": direct_answer_mode,
        "answer": answer,
        "human_approved": human_approved,
        "enable_human_interrupt": True,
        "top_k": top_k,
        "trace_id": _trace_id(user_id, conversation_id, user_input),
        "events": [],
    }


def prepare_langgraph_chat_context(
    *,
    user_id: bytes,
    conversation_id: str,
    user_input: str,
    profile_context: str = "",
    direct_answer_mode: bool = False,
    top_k: int = 5,
) -> Dict[str, Any]:
    state = make_initial_state(
        user_id=user_id,
        conversation_id=conversation_id,
        user_input=user_input,
        profile_context=profile_context,
        direct_answer_mode=direct_answer_mode,
        top_k=top_k,
    )
    config = {"configurable": {"thread_id": state["trace_id"]}}
    result = dict(get_pre_answer_graph().invoke(state, config=config))
    pending = _interrupt_payload(result)
    if pending:
        result["human_status"] = "needs_human"
        result["human_interrupt"] = pending
    return result


def _interrupt_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pending = result.get("__interrupt__") or []
    if not pending:
        return None
    value = getattr(pending[0], "value", pending[0])
    return dict(value) if isinstance(value, dict) else {"message": str(value)}


def resume_langgraph_chat_context(
    *,
    trace_id: str,
    decision: Dict[str, Any],
) -> Dict[str, Any]:
    """Resume a native LangGraph interrupt in the worker that owns its checkpoint."""
    config = {"configurable": {"thread_id": trace_id}}
    result = get_pre_answer_graph().invoke(Command(resume=decision), config=config)
    return dict(result)


def rebuild_approved_langgraph_chat_context(
    *,
    user_id: bytes,
    conversation_id: str,
    user_input: str,
    profile_context: str = "",
    direct_answer_mode: bool = False,
    top_k: int = 5,
    decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rebuild an approved checkpoint when resume lands on another worker."""
    state = make_initial_state(
        user_id=user_id,
        conversation_id=conversation_id,
        user_input=user_input,
        profile_context=profile_context,
        direct_answer_mode=direct_answer_mode,
        human_approved=True,
        top_k=top_k,
    )
    state["human_feedback"] = str((decision or {}).get("feedback") or "")
    config = {"configurable": {"thread_id": f"{state['trace_id']}:approved"}}
    return dict(get_pre_answer_graph().invoke(state, config=config))


def judge_langgraph_chat_answer(answer: str, context: Dict[str, Any]) -> Dict[str, Any]:
    state: AgentState = dict(context)
    state["answer"] = answer or ""
    before = len(state.get("events") or [])
    result = judge_node(state)
    result["judge_event"] = (result.get("events") or [])[before:] and (result.get("events") or [])[before]
    return result.get("judge") or {}


def run_single_agent(agent_id: AgentId, state: AgentState) -> AgentState:
    """Run one node independently. Missing prerequisites are handled locally."""
    if agent_id == "full":
        state = dict(state)
        state["enable_human_interrupt"] = False
        thread_id = state.get("trace_id") or _trace_id(
            state.get("user_id_bytes", b""),
            state.get("conversation_id", "single-agent"),
            state.get("user_input", ""),
        )
        return dict(get_full_graph().invoke(
            state, config={"configurable": {"thread_id": f"single:{thread_id}"}},
        ))
    runners = {
        "diagnosis": diagnosis_node,
        "retrieval": retrieval_node,
        "rules": rules_node,
        "human_gate": human_gate_node,
        "judge": judge_node,
    }
    runner = runners.get(agent_id)
    if runner is None:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    if agent_id in {"retrieval", "rules", "human_gate", "judge"} and not state.get("diagnosis"):
        state = diagnosis_node(state)
    if agent_id in {"rules", "human_gate", "judge"} and "evidence_refs" not in state:
        state = retrieval_node(state)
    if agent_id in {"human_gate", "judge"} and "rule_hits" not in state:
        state = rules_node(state)
    return runner(state)


def list_langgraph_agents() -> List[Dict[str, str]]:
    return [
        {"id": "diagnosis", "name": TEXT["diagnosis_agent"], "description": "\u8bc6\u522b\u610f\u56fe\u3001\u5b66\u4e60\u8005\u72b6\u6001\u548c\u4efb\u52a1\u98ce\u9669"},
        {"id": "retrieval", "name": TEXT["retrieval_agent"], "description": "\u68c0\u7d22\u7528\u6237\u77e5\u8bc6\u5e93\u5e76\u751f\u6210\u53c2\u8003\u6765\u6e90"},
        {"id": "rules", "name": TEXT["rules_agent"], "description": "\u68c0\u67e5\u8bc1\u636e\u3001\u76f4\u63a5\u89e3\u91ca\u548c\u6765\u6e90\u5c55\u793a\u89c4\u5219"},
        {"id": "human_gate", "name": TEXT["human_agent"], "description": "\u5bf9\u8d44\u6599\u4e0d\u8db3\u6216\u98ce\u9669\u573a\u666f\u6807\u8bb0\u4eba\u5de5\u786e\u8ba4"},
        {"id": "judge", "name": TEXT["judge_agent"], "description": "\u68c0\u67e5\u6700\u7ec8\u56de\u7b54\u7684\u98ce\u9669\u3001\u53ef\u4fe1\u5ea6\u548c\u6765\u6e90\u4f7f\u7528"},
        {"id": "full", "name": "LangGraph full run", "description": "diagnosis -> retrieval -> rules -> human_gate -> judge"},
    ]
