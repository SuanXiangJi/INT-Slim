# -*- coding: utf-8 -*-
"""
学情诊断 Agent (Diagnosis Agent)

Analyzes learner state: profile, mastery, errors, cognitive load.
Reads from DB via CRUD, outputs learner portrait + mastery summary.
"""
from __future__ import annotations
import json
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.learner import (
    get_learner, get_learner_by_name, list_learners,
    get_mastery, get_errors, get_cognitive_load, create_learner
)
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)

DIAGNOSTIC_PROMPT = """你是一位学情诊断专家。请根据以下学员数据，用中文输出诊断结果。

学员基本信息：
{learner_info}

掌握度数据：
{mastery_data}

错误记录：
{error_data}

认知负荷：{load_info}

请分析并输出：
1. 学员当前整体掌握水平（掌握较好/一般/薄弱的知识点）
2. 薄弱环节与常见错误类型
3. 建议的学习策略（难度建议、重点方向）
4. 当前认知负荷状态是否适合开始新学习

以JSON格式输出：
{{"summary": "整体诊断摘要", "strengths": ["优势点1", "..."], "weaknesses": ["薄弱点1", "..."], "suggested_difficulty": 0.0-1.0, "load_status": "ok/overloaded", "focus_areas": ["重点方向1", "..."]}}
"""


class DiagnosisAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "diagnosis"

    @property
    def name(self) -> str:
        return "学情诊断"

    @property
    def description(self) -> str:
        return "分析学员画像、掌握度、错误模式和认知负荷，输出诊断结果"

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[DiagnosisAgent] Starting diagnosis for user=%s", state.user_id)
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            # 1. Find or create learner
            learner = get_learner_by_name(db, state.user_id[:8])
            if not learner:
                learner = create_learner(db, name=state.user_id[:8])
            lid = bytes_to_uuid_string(learner.id)

            # 2. Get mastery data
            mastery_rows = get_mastery(db, lid)
            error_rows = get_errors(db, lid)
            load_obj = get_cognitive_load(db, lid)

            # 3. Build state
            state.learner_profile = {
                "id": lid, "name": learner.name,
                "grade": learner.grade, "language": learner.language,
                "goals": learner.goals or [], "tags": learner.tags or [],
            }
            state.learner_mastery = {
                r.kp_id: {"level": r.level, "confidence": r.confidence}
                for r in mastery_rows
            }
            state.cognitive_load = load_obj.current_load if load_obj else 0.0

            # 4. LLM diagnosis
            mastery_data = json.dumps(state.learner_mastery, ensure_ascii=False, indent=2)[:2000]
            error_data = json.dumps(
                [{"type": e.error_type, "kp_id": e.kp_id, "count": int(e.count)} for e in error_rows],
                ensure_ascii=False, indent=2)[:1000]
            load_info = f"当前负荷: {state.cognitive_load:.2f} / 阈值: {(load_obj.threshold if load_obj else 0.8):.2f}"

            prompt = DIAGNOSTIC_PROMPT.format(
                learner_info=json.dumps(state.learner_profile, ensure_ascii=False)[:1000],
                mastery_data=mastery_data,
                error_data=error_data,
                load_info=load_info,
            )

            response = await llm_service.chat_async(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.3,
            )
            result_text = response.get("content", "{}")
            # Extract JSON from response
            import re
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                state.mastery_summary = result.get("summary", result_text[:500])
                state.learner_profile["suggested_difficulty"] = result.get("suggested_difficulty", 0.5)
                state.learner_profile["load_status"] = result.get("load_status", "ok")
                state.learner_profile["focus_areas"] = result.get("focus_areas", [])
            else:
                state.mastery_summary = result_text[:500]

            logger.info("[DiagnosisAgent] Diagnosis complete: %s", state.mastery_summary[:80])
        except Exception as e:
            logger.exception("[DiagnosisAgent] Error")
            state.errors.append({"agent": "diagnosis", "error": str(e)})
            state.mastery_summary = "诊断过程出现错误，请重试"
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield thinking event, then run process."""
        yield {"type": "thinking", "data": {"agent": "diagnosis", "content": "正在分析学员画像与掌握度..."}}
        state = await self.process(state)
        yield {"type": "diagnosis_result", "data": {
            "summary": state.mastery_summary,
            "learner_profile": state.learner_profile,
        }}