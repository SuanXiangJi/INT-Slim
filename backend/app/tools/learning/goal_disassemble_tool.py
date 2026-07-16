# -*- coding: utf-8 -*-
"""Goal Disassemble Tool - DB-backed learning plan creation."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.plan import create_plan, get_plan, list_plans
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class GoalDisassembleTool(BaseTool):
    """目标拆解工具"""

    @property
    def id(self) -> str:
        return "goal_disassemble"

    @property
    def name(self) -> str:
        return "目标拆解"

    @property
    def description(self) -> str:
        return (
            "将高层次学习目标拆解为可执行的技能点序列和资源需求。"
            "operation 支持: "
            "disassemble(拆解), get_plan(获取计划), list_plans(列出计划)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["disassemble", "get_plan", "list_plans"],
                    "description": "要执行的操作"
                },
                "learner_id": {
                    "type": "string",
                    "description": "学习者ID"
                },
                "plan_id": {
                    "type": "string",
                    "description": "计划ID"
                },
                "goal": {
                    "type": "string",
                    "description": "学习目标"
                }
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")

            if op == "disassemble":
                learner_id = params.get("learner_id", "")
                goal = params.get("goal", "")
                if not learner_id:
                    return {"success": False, "error": "learner_id required"}
                obj = create_plan(db, learner_id, goal)
                return {"success": True, "plan_id": bytes_to_uuid_string(obj.id),
                    "goal": obj.goal, "status": obj.status}

            elif op == "get_plan":
                plan_id = params.get("plan_id", "")
                if not plan_id:
                    return {"success": False, "error": "plan_id required"}
                obj = get_plan(db, plan_id)
                if not obj:
                    return {"success": False, "error": "plan not found"}
                return {"success": True,
                    "plan_id": bytes_to_uuid_string(obj.id),
                    "goal": obj.goal, "status": obj.status,
                    "created_at": obj.created_at.isoformat() if obj.created_at else ""}

            elif op == "list_plans":
                learner_id = params.get("learner_id")
                objs = list_plans(db, learner_id)
                plans = [{
                    "plan_id": bytes_to_uuid_string(o.id),
                    "goal": o.goal, "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else ""
                } for o in objs]
                return {"success": True, "plans": plans, "total": len(plans)}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("goal_disassemble error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()