# -*- coding: utf-8 -*-
"""
审核 Agent (Review Agent)

Checks generated content for factual accuracy, rule compliance, and suitability.
Uses LLM + rule engine for quality assessment.
"""
from __future__ import annotations
import json, logging, re
from typing import AsyncGenerator, Dict, Any
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.review import create_review, add_defect

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """你是一位内容质量审核专家。请审核以下候选教学内容。

学员诊断：{diagnosis}
目标：{goal}
候选内容：{candidate}

审核规则：
1. 事实准确性：内容是否基于检索到的证据？有无幻觉？
2. 规范性：结构是否完整？难度是否适配学员？
3. 清晰性：表述是否清晰易懂？
4. 安全性：是否有不适当内容？

以JSON格式输出审核结果：
{{
    "verdict": "approved/rejected/needs_revision",
    "overall_score": 0-100,
    "defects": [{{"type": "factual/normative/adaptability/clarity", "severity": "critical/major/minor", "location": "问题位置", "description": "问题描述", "suggestion": "修改建议"}}],
    "risk_level": "low/medium/high",
    "summary": "审核总结"
}}
"""


class ReviewAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "review"

    @property
    def name(self) -> str:
        return "质量审核"

    @property
    def description(self) -> str:
        return "检查候选内容的事实准确性、规范性和适配性"

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[ReviewAgent] Reviewing %d candidates...", len(state.candidates))
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            all_defects = []
            review_summaries = []

            for i, cand in enumerate(state.candidates):
                prompt = REVIEW_PROMPT.format(
                    diagnosis=state.mastery_summary or "无诊断数据",
                    goal=state.goal or state.user_input[:200],
                    candidate=json.dumps(cand, ensure_ascii=False)[:3000],
                )

                response = await llm_service.chat_async(
                    messages=[{"role": "user", "content": prompt}],
                    model="default", temperature=0.3,
                )
                result_text = response.get("content", "{}")
                match = re.search(r"\{.*\}", result_text, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                    defects = result.get("defects", [])
                    for d in defects:
                        d["candidate_index"] = i
                        d["candidate_type"] = cand.get("type", "")
                    all_defects.extend(defects)

                    # Save review to DB
                    if cand.get("db_id"):
                        rv = create_review(db,
                            content_id=cand["db_id"],
                            reviewer_type="auto",
                            risk_level=result.get("risk_level", "medium"))
                        from app.utils.uuid import bytes_to_uuid_string
                        review_id = bytes_to_uuid_string(rv.id)
                        for d in defects[:5]:
                            add_defect(db, review_id,
                                defect_type=d.get("type", "clarity"),
                                severity=d.get("severity", "minor"),
                                location=d.get("location", ""),
                                description=d.get("description", ""),
                                suggestion=d.get("suggestion", ""))

                    review_summaries.append(result.get("summary", ""))

            state.defects = all_defects
            state.review_summary = "; ".join(review_summaries) if review_summaries else "审核完成"
            logger.info("[ReviewAgent] Found %d defects across %d candidates",
                        len(all_defects), len(state.candidates))
        except Exception as e:
            logger.exception("[ReviewAgent] Error")
            state.errors.append({"agent": "review", "error": str(e)})
            state.review_summary = "审核过程出错"
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "thinking", "data": {"agent": "review", "content": "正在审核候选内容质量..."}}
        state = await self.process(state)
        yield {"type": "review_result", "data": {
            "defect_count": len(state.defects),
            "summary": state.review_summary,
        }}