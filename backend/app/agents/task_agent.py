# -*- coding: utf-8 -*-
"""
任务理解 Agent (Task Agent)

Decomposes high-level learning goals into executable skill sequences.
Uses LLM + skill graph to create structured learning plans.
"""
from __future__ import annotations
import json, logging, re
from typing import AsyncGenerator, Dict, Any
from app.agents.base import BaseAgent, GraphState
from app.services.llm_service import llm_service
from app.crud.learning.knowledge_point import search_kps, get_prerequisites, get_next_kps
from app.crud.learning.plan import create_plan, list_plans

logger = logging.getLogger(__name__)

TASK_PROMPT = """你是一位教学设计师。学员的诊断结果和目标是：

学员诊断摘要：{diagnosis_summary}
学员目标/输入：{user_input}
现有知识点：{available_kps}

请将目标拆解为可执行的知识点学习序列。要求：
1. 根据诊断结果调整难度
2. 按前置依赖关系排序
3. 每个知识点给出建议的学习时长（小时）

以JSON格式输出：
{{"plan_name": "计划名称", "goal": "学习目标描述", "skills": [{{"kp_id": "知识点ID或名称", "name": "知识点名称", "estimated_hours": 4, "difficulty": 0.5, "reason": "为什么学这个"}}], "total_hours": 总小时数, "weekly_schedule": "周度建议"}}
"""


class TaskAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "task"

    @property
    def name(self) -> str:
        return "任务理解"

    @property
    def description(self) -> str:
        return "将学习目标拆解为可执行的知识点序列和计划"

    async def process(self, state: GraphState) -> GraphState:
        logger.info("[TaskAgent] Decomposing goal for user=%s", state.user_id)
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            # 1. Search for relevant KPs
            goal = state.goal or state.user_input
            kp_results = search_kps(db, goal[:50], limit=20)
            available_kps = [
                {"id": k.id, "name": k.name, "category": k.category, "difficulty": k.difficulty}
                for k in kp_results
            ]

            # 2. LLM decomposes the goal
            prompt = TASK_PROMPT.format(
                diagnosis_summary=state.mastery_summary or "新学员，无历史数据",
                user_input=state.user_input[:500],
                available_kps=json.dumps(available_kps[:15], ensure_ascii=False),
            )

            response = await llm_service.chat_async(
                messages=[{"role": "user", "content": prompt}],
                model="default", temperature=0.3,
            )
            result_text = response.get("content", "{}")

            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                state.goal = result.get("goal", goal)
                state.skill_sequence = result.get("skills", [])
                state.resource_requirements = {
                    "total_hours": result.get("total_hours", 0),
                    "weekly_schedule": result.get("weekly_schedule", ""),
                    "plan_name": result.get("plan_name", ""),
                }

                # 3. Save as learning plan in DB
                if state.learner_profile and state.learner_profile.get("id"):
                    plan = create_plan(db, state.learner_profile["id"], state.goal)
                    from app.utils.uuid import bytes_to_uuid_string
                    state.resource_requirements["plan_id"] = bytes_to_uuid_string(plan.id)
                    logger.info("[TaskAgent] Plan created: %s", state.resource_requirements["plan_id"])
            else:
                state.skill_sequence = [{"name": goal, "estimated_hours": 0}]

            logger.info("[TaskAgent] Decomposed into %d skills", len(state.skill_sequence))
        except Exception as e:
            logger.exception("[TaskAgent] Error")
            state.errors.append({"agent": "task", "error": str(e)})
            state.skill_sequence = [{"name": goal[:100], "error": str(e)}]
        finally:
            db.close()
        return state

    async def process_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "thinking", "data": {"agent": "task", "content": "正在拆解学习目标为知识序列..."}}
        state = await self.process(state)
        yield {"type": "task_result", "data": {
            "goal": state.goal,
            "skills": state.skill_sequence,
            "total_hours": state.resource_requirements.get("total_hours", 0),
        }}