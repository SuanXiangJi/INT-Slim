# -*- coding: utf-8 -*-
"""
裁判 Agent (Judge Agent)

Makes final decision among multiple content candidates.
Selects best version based on review quality, risk assessment, and learner fit.
"""
from __future__ import annotations
import json, logging, re
from typing import AsyncGenerator, Dict, Any
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.candidate import list_candidates, select_candidate
from app.crud.learning.content import update_content_status

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一位教学决策专家。你需要从多个候选方案中选择最佳版本。

学员诊断：{diagnosis}
学习目标：{goal}
审核结果：{review_summary}

候选方案：
{candidates_with_reviews}

请分析并输出最终决策：
{{
    "selected_index": 0-{max_idx},
    "selection_reasoning": "为什么选择这个方案",
    "risk_assessment": {{"level": "low/medium/high", "details": "风险说明"}},
    "final_content_type": "lecture/practice/quiz",
    "adaptation_notes": "对最终内容的微调建议"
}}
"""


class JudgeAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "judge"

    @property
    def name(self) -> str:
        return "内容裁决"

    @property
    def description(self) -> str:
        return "综合审核意见和学员画像，从多个候选内容中做出最终选择"

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[JudgeAgent] Judging %d candidates...", len(state.candidates))
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            if not state.candidates:
                state.judge_reasoning = "没有候选内容可供裁决"
                return state

            candidates_str = json.dumps([
                {"idx": i, "type": c.get("type"), "title": c.get("title"),
                 "has_evidence": bool(c.get("evidence_map"))}
                for i, c in enumerate(state.candidates)
            ], ensure_ascii=True)

            prompt = JUDGE_PROMPT.format(
                diagnosis=state.mastery_summary or "无诊断",
                goal=state.goal or state.user_input[:200],
                review_summary=state.review_summary or "无审核",
                candidates_with_reviews=candidates_str,
                max_idx=len(state.candidates) - 1,
            )

            response = await llm_service.chat_async(
                messages=[{"role": "user", "content": prompt}],
                model="default", temperature=0.3,
            )
            result_text = response.get("content", "{}")
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                selected_idx = result.get("selected_index", 0)
                if 0 <= selected_idx < len(state.candidates):
                    state.final_content = state.candidates[selected_idx]
                    state.judge_reasoning = result.get("selection_reasoning", "")
                    state.risk_assessment = result.get("risk_assessment", {"level": "low"})

                    # Update DB: mark the selected candidate
                    selected = state.candidates[selected_idx]
                    if selected.get("db_id"):
                        update_content_status(db, selected["db_id"], "published")

                    # Find and select the corresponding ranking
                    from app.utils.uuid import uuid_string_to_bytes, bytes_to_uuid_string
                    rankings = list_candidates(db)
                    for r in rankings:
                        if r.content_id == selected.get("db_id"):
                            select_candidate(db, bytes_to_uuid_string(r.id))
                            break
                else:
                    state.final_content = state.candidates[0] if state.candidates else None
                    state.judge_reasoning = f"选择的索引 {selected_idx} 超出范围，默认选择第一个"

                logger.info("[JudgeAgent] Selected candidate #%d: %s",
                            selected_idx, state.final_content.get("title", "") if state.final_content else "None")
            else:
                state.final_content = state.candidates[0] if state.candidates else None
                state.judge_reasoning = "解析失败，默认选择第一个"

        except Exception as e:
            logger.exception("[JudgeAgent] Error")
            state.errors.append({"agent": "judge", "error": str(e)})
            state.final_content = state.candidates[0] if state.candidates else None
            state.judge_reasoning = f"裁决出错: {e}"
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "thinking", "data": {"agent": "judge", "content": "正在综合评审结果做出最终裁决..."}}
        state = await self.process(state)
        yield {"type": "judge_result", "data": {
            "selected": state.final_content.get("title", "") if state.final_content else "无",
            "reasoning": state.judge_reasoning,
            "risk": state.risk_assessment,
        }}