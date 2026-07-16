# -*- coding: utf-8 -*-
"""
生成 Agent (Generation Agent)

Generates learning content (lecture, practice, quiz) with evidence citations.
Uses LLM + evidence from retrieval agent to create structured content.
"""
from __future__ import annotations
import json, logging, re
from typing import AsyncGenerator, Dict, Any
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.content import create_content
from app.crud.learning.exam import create_exam, add_question
from app.crud.learning.candidate import create_candidate

logger = logging.getLogger(__name__)

GENERATION_PROMPT = """你是一位教学内容生成专家。请根据以下信息生成个性化学习内容。

学员诊断：{diagnosis}
学习目标：{goal}
技能序列：{skills}
检索到的证据参考：{evidence}
知识图谱关系：{graph}

请生成三部分内容，以JSON格式输出：
{{
    "lecture": {{"title": "讲义标题", "sections": [{{"heading": "小节标题", "body": "正文内容（引用证据标注[来源:xxx]）"}}]}},
    "practice": {{"title": "实操练习", "steps": [{{"step": 1, "instruction": "步骤说明"}}]}},
    "quiz": [{{"question": "题目", "options": ["A", "B", "C"], "answer": "A", "explanation": "解析"}}],
    "evidence_map": [{{"claim": "内容中的主张", "source": "证据来源", "confidence": "high/medium/low"}}]
}}
"""


class GenerationAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "generation"

    @property
    def name(self) -> str:
        return "内容生成"

    @property
    def description(self) -> str:
        return "基于证据和规则生成个性化教学讲义、练习和测验"

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[GenerationAgent] Generating content...")
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            skills_str = json.dumps(
                [{"name": s.get("name"), "difficulty": s.get("difficulty", 0.5)}
                 for s in state.skill_sequence[:5]], ensure_ascii=False)
            evidence_str = json.dumps(
                [{"source": e["source"], "title": e["title"]}
                 for e in state.evidence[:10]], ensure_ascii=False)
            graph_str = json.dumps(
                [{"from": g.get("from_name"), "to": g.get("to_name"), "rel": g.get("relation")}
                 for g in state.graph_relations[:10]], ensure_ascii=False)

            prompt = GENERATION_PROMPT.format(
                diagnosis=state.mastery_summary or "新学员",
                goal=state.goal or state.user_input[:200],
                skills=skills_str or "无",
                evidence=evidence_str or "无检索结果，基于通用知识",
                graph=graph_str or "无",
            )

            response = await llm_service.chat_async(
                messages=[{"role": "user", "content": prompt}],
                model="default", temperature=0.5,
            )
            result_text = response.get("content", "{}")
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                result = json.loads(match.group())

                # Store as candidates for review
                candidates = []
                for ctype in ["lecture", "practice", "quiz"]:
                    content_data = result.get(ctype, {})
                    if content_data:
                        candidate = {
                            "type": ctype,
                            "title": content_data.get("title", f"{ctype}内容"),
                            "content": content_data,
                            "evidence_map": result.get("evidence_map", []),
                        }
                        candidates.append(candidate)
                state.candidates = candidates

                # Save to DB
                plan_id = state.resource_requirements.get("plan_id")
                lid = state.learner_profile.get("id") if state.learner_profile else None

                for cand in candidates:
                    c = create_content(db,
                        template_type=cand["type"],
                        title=cand["title"],
                        content_data=cand,
                        plan_id=plan_id,
                        kp_id=None)
                    from app.utils.uuid import bytes_to_uuid_string
                    cand["db_id"] = bytes_to_uuid_string(c.id)

                    # Create candidate ranking entry
                    create_candidate(db,
                        content_id=cand["db_id"],
                        rank_score=0.5,
                        risk_info={"evidence_count": len(cand.get("evidence_map", []))})

                logger.info("[GenerationAgent] Generated %d candidates", len(candidates))
            else:
                state.candidates = [{"type": "text", "content": result_text[:1000]}]

        except Exception as e:
            logger.exception("[GenerationAgent] Error")
            state.errors.append({"agent": "generation", "error": str(e)})
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "thinking", "data": {"agent": "generation", "content": "正在根据检索证据生成学习内容..."}}
        state = await self.process(state)
        yield {"type": "generation_result", "data": {
            "candidate_count": len(state.candidates),
            "types": [c.get("type") for c in state.candidates],
        }}