# -*- coding: utf-8 -*-
"""
检索 Agent (Retrieval Agent)

Retrieves evidence from knowledge base, skill graph, and rules.
Uses knowledge_search_tool and CRUD for data access.
"""
from __future__ import annotations
import json, logging, re, os
from typing import AsyncGenerator, Dict, Any, List
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.knowledge_point import get_kp, get_prerequisites

logger = logging.getLogger(__name__)

# Path to demo knowledge base
_DEMO_KB = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "sandbox", "demo_kb", "knowledge"
))

RETRIEVAL_PROMPT = """你是一位知识检索专家。需要为以下学习任务检索相关资料。

学习目标：{goal}
技能序列：{skill_sequence}
诊断摘要：{diagnosis_summary}

知识库中有以下课程/资料：
{kb_summary}

技能图谱关系：
{graph_relations}

请整理需要检索的关键证据，按知识点分组输出JSON：
{{"retrieval_plan": [{{"kp_name": "知识点名", "search_queries": ["查询词1", "..."], "priority": "high/medium/low"}}], "total_sources_needed": 数量}}
"""


class RetrievalAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "retrieval"

    @property
    def name(self) -> str:
        return "知识检索"

    @property
    def description(self) -> str:
        return "从知识库、技能图谱和规则库检索学习证据"

    def _search_kb(self, query: str, limit: int = 3) -> List[Dict]:
        """Simple keyword search in demo KB JSON files."""
        results = []
        kb_root = _DEMO_KB
        if not os.path.isdir(kb_root):
            return results
        courses_dir = os.path.join(kb_root, "courses")
        if not os.path.isdir(courses_dir):
            return results
        q = query.lower()
        import glob
        for fn in sorted(glob.glob(os.path.join(courses_dir, "*.json"))):
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    course = json.load(f)
                matched = [
                    {"slug": p["slug"], "title": p["title"], "summary": p.get("summary", "")[:200]}
                    for p in course.get("pages", [])
                    if q in p.get("title", "").lower() or q in p.get("summary", "").lower()
                ]
                if matched:
                    results.append({
                        "course_id": course.get("id", ""),
                        "course_name": course.get("name", ""),
                        "matches": matched[:3],
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue
        return results

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[RetrievalAgent] Retrieving evidence...")
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            all_evidence = []
            # 1. Search KB for each skill in sequence
            search_terms = set()
            for sk in state.skill_sequence:
                name = sk.get("name", "") or sk.get("kp_id", "")
                if name:
                    search_terms.add(name[:30])
            if state.goal:
                search_terms.add(state.goal[:30])

            for term in list(search_terms)[:5]:
                results = self._search_kb(term)
                for r in results:
                    for m in r.get("matches", []):
                        all_evidence.append({
                            "source": r["course_name"],
                            "title": m["title"],
                            "summary": m["summary"],
                            "relevance": term,
                        })

            state.evidence = all_evidence[:20]

            # 2. Get graph relations for skills
            graph_relations = []
            for sk in state.skill_sequence[:5]:
                kp_id = sk.get("kp_id", "")
                if kp_id:
                    prereqs = get_prerequisites(db, kp_id)
                    nexts = get_next_kps(db, kp_id)
                    for p in prereqs:
                        if p:
                            graph_relations.append({
                                "from": p.id, "from_name": p.name,
                                "to": kp_id, "to_name": sk.get("name", ""),
                                "relation": "prerequisite"
                            })
            state.graph_relations = graph_relations[:20]

            # 3. Generate knowledge summary
            kb_summary = f"检索到 {len(all_evidence)} 条相关文档，{len(graph_relations)} 条图谱关系"
            state.knowledge_summary = kb_summary
            logger.info("[RetrievalAgent] Found %d evidence items, %d relations",
                        len(all_evidence), len(graph_relations))

        except Exception as e:
            logger.exception("[RetrievalAgent] Error")
            state.errors.append({"agent": "retrieval", "error": str(e)})
            state.knowledge_summary = "检索过程出错"
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "thinking", "data": {"agent": "retrieval", "content": "正在检索知识库和技能图谱..."}}
        state = await self.process(state)
        yield {"type": "retrieval_result", "data": {
            "evidence_count": len(state.evidence),
            "relations_count": len(state.graph_relations),
            "summary": state.knowledge_summary,
        }}