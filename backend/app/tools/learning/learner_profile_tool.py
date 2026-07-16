# -*- coding: utf-8 -*-
"""Learner Profile Tool - DB-backed learner CRUD, mastery, errors, cognitive load."""
import uuid
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.learner import (
    create_learner, get_learner, get_learner_by_name, list_learners,
    update_learner, record_mastery, record_error, update_cognitive_load,
    get_mastery, get_errors, get_cognitive_load
)
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class LearnerProfileTool(BaseTool):
    """学习者画像工具"""

    @property
    def id(self) -> str:
        return "learner_profile"

    @property
    def name(self) -> str:
        return "学习者画像"

    @property
    def description(self) -> str:
        return (
            "管理学习者画像数据。包括：创建/读取/更新画像、记录掌握度、"
            "记录错误类型、更新认知负荷阈值。operation 支持: "
            "create(创建), get(读取), update(更新), record_mastery(记录掌握度), "
            "record_error(记录错误), update_load(更新负荷), list(列出所有学员)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "get", "update", "record_mastery",
                             "record_error", "update_load", "list"],
                    "description": "要执行的操作"
                },
                "learner_id": {
                    "type": "string",
                    "description": "学习者唯一标识（创建时不填则自动生成）"
                },
                "profile": {
                    "type": "object",
                    "description": "画像数据（用于 create/update）",
                    "properties": {
                        "name": {"type": "string"},
                        "grade": {"type": "string", "description": "年级/班级"},
                        "language": {"type": "string", "default": "zh-CN"},
                        "goals": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "skill_id": {
                    "type": "string",
                    "description": "技能/知识点标识（用于 record_mastery/record_error）"
                },
                "mastery_level": {
                    "type": "number",
                    "description": "掌握度 0.0~1.0",
                    "minimum": 0, "maximum": 1
                },
                "confidence": {
                    "type": "number",
                    "description": "置信度 0.0~1.0",
                    "minimum": 0, "maximum": 1, "default": 0.5
                },
                "error_type": {
                    "type": "string",
                    "description": "错误类型（用于 record_error），如 concept_misunderstanding / calculation / logic / carelessness"
                },
                "load_value": {
                    "type": "number",
                    "description": "认知负荷估计值（用于 update_load）"
                }
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")
            learner_id = params.get("learner_id", "")
            profile = params.get("profile", {}) or {}

            if op == "create":
                name = profile.get("name") or params.get("name") or "learner_" + str(uuid.uuid4())[:8]
                existing = get_learner_by_name(db, name)
                if existing:
                    return {"success": True, "learner_id": bytes_to_uuid_string(existing.id),
                            "message": "learner already exists, use get to retrieve"}
                obj = create_learner(db, name=name,
                    grade=profile.get("grade"),
                    language=profile.get("language", "zh-CN"),
                    goals=profile.get("goals"),
                    tags=profile.get("tags"))
                return {"success": True, "learner_id": bytes_to_uuid_string(obj.id)}

            elif op == "get":
                if not learner_id:
                    return {"success": False, "error": "learner_id required"}
                obj = get_learner(db, learner_id)
                if not obj:
                    return {"success": False, "error": f"learner {learner_id} not found"}
                lid = bytes_to_uuid_string(obj.id)
                mastery_rows = get_mastery(db, lid)
                error_rows = get_errors(db, lid)
                load_obj = get_cognitive_load(db, lid)
                return {
                    "success": True, "learner_id": lid,
                    "data": {
                        "name": obj.name, "grade": obj.grade,
                        "language": obj.language,
                        "goals": obj.goals or [], "tags": obj.tags or [],
                        "mastery": {
                            r.kp_id: {
                                "level": r.level, "confidence": r.confidence,
                                "last_assessed": r.last_assessed.isoformat() if r.last_assessed else ""
                            } for r in mastery_rows
                        },
                        "errors": [
                            {"type": r.error_type, "kp_id": r.kp_id,
                             "count": r.count,
                             "last_occurrence": r.last_occurrence.isoformat() if r.last_occurrence else ""}
                            for r in error_rows
                        ],
                        "current_load": load_obj.current_load if load_obj else 0.0
                    }
                }

            elif op == "update":
                if not learner_id:
                    return {"success": False, "error": "learner_id required"}
                obj = update_learner(db, learner_id,
                    name=profile.get("name"), grade=profile.get("grade"),
                    language=profile.get("language"),
                    goals=profile.get("goals"), tags=profile.get("tags"))
                if not obj:
                    return {"success": False, "error": f"learner {learner_id} not found"}
                return {"success": True, "learner_id": bytes_to_uuid_string(obj.id)}

            elif op == "record_mastery":
                if not learner_id or not params.get("skill_id"):
                    return {"success": False, "error": "learner_id and skill_id required"}
                obj = record_mastery(db, learner_id, params["skill_id"],
                    params.get("mastery_level", 0.5),
                    params.get("confidence", 0.5))
                return {"success": True, "learner_id": bytes_to_uuid_string(obj.learner_id),
                    "skill_id": obj.kp_id, "level": obj.level}

            elif op == "record_error":
                if not learner_id:
                    return {"success": False, "error": "learner_id required"}
                obj = record_error(db, learner_id,
                    params.get("error_type", "general"),
                    params.get("skill_id"))
                return {"success": True, "learner_id": bytes_to_uuid_string(obj.learner_id),
                    "error_type": obj.error_type, "count": int(obj.count)}

            elif op == "update_load":
                if not learner_id:
                    return {"success": False, "error": "learner_id required"}
                obj = update_cognitive_load(db, learner_id,
                    params.get("load_value", 0.5))
                return {"success": True, "learner_id": bytes_to_uuid_string(obj.learner_id),
                    "current_load": obj.current_load}

            elif op == "list":
                objs = list_learners(db)
                items = []
                for o in objs:
                    lid = bytes_to_uuid_string(o.id)
                    mcount = len(get_mastery(db, lid))
                    ecount = len(get_errors(db, lid))
                    items.append({
                        "learner_id": lid, "name": o.name,
                        "mastery_count": mcount,
                        "error_count": ecount,
                        "updated_at": o.updated_at.isoformat() if o.updated_at else ""
                    })
                return {"success": True, "learners": items, "total": len(items)}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("learner_profile error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()