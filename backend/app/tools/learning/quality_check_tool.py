# -*- coding: utf-8 -*-
"""Quality Check Tool - DB-backed quality reviews with defects."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.review import (
    create_review, get_review, list_reviews,
    update_review_status, add_defect, list_defects
)
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class QualityCheckTool(BaseTool):
    """质量审核工具"""

    @property
    def id(self) -> str:
        return "quality_check"

    @property
    def name(self) -> str:
        return "质量审核"

    @property
    def description(self) -> str:
        return (
            "审核学习内容的质量：事实准确性、规范性、适配性。"
            "operation 支持: "
            "new_review(创建审核), get(获取审核结果), list(列出审核记录), "
            "add_defect(添加缺陷), update_verdict(更新裁决)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["new_review", "get", "list", "add_defect", "update_verdict"],
                    "description": "要执行的操作"
                },
                "content_id": {"type": "string", "description": "内容ID"},
                "review_id": {"type": "string", "description": "审核ID"},
                "reviewer_type": {"type": "string", "default": "auto",
                    "description": "审核者类型: auto/expert/peer"},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                "defect_type": {"type": "string", "enum": ["factual", "normative", "adaptability", "clarity"]},
                "severity": {"type": "string", "enum": ["critical", "major", "minor"], "default": "minor"},
                "location": {"type": "string", "description": "缺陷位置"},
                "description": {"type": "string", "description": "缺陷描述"},
                "suggestion": {"type": "string", "description": "修改建议"},
                "verdict": {"type": "string", "description": "裁决: approved/rejected/needs_revision"},
                "summary": {"type": "string", "description": "审核摘要"}
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")

            if op == "new_review":
                obj = create_review(db,
                    content_id=params.get("content_id", ""),
                    reviewer_type=params.get("reviewer_type", "auto"),
                    risk_level=params.get("risk_level", "medium"))
                return {"success": True, "review_id": bytes_to_uuid_string(obj.id),
                    "status": obj.status}

            elif op == "get":
                rid = params.get("review_id", "")
                if not rid:
                    return {"success": False, "error": "review_id required"}
                obj = get_review(db, rid)
                if not obj:
                    return {"success": False, "error": "review not found"}
                defects = list_defects(db, rid)
                return {"success": True,
                    "review_id": bytes_to_uuid_string(obj.id),
                    "status": obj.status, "risk_level": obj.risk_level,
                    "review_summary": obj.review_summary,
                    "defects": [{"defect_type": d.defect_type, "severity": d.severity,
                        "location": d.location, "description": d.description,
                        "suggestion": d.suggestion} for d in defects]}

            elif op == "list":
                objs = list_reviews(db, content_id=params.get("content_id"))
                reviews = [{
                    "review_id": bytes_to_uuid_string(o.id),
                    "status": o.status, "risk_level": o.risk_level,
                    "created_at": o.created_at.isoformat() if o.created_at else ""
                } for o in objs]
                return {"success": True, "reviews": reviews, "total": len(reviews)}

            elif op == "add_defect":
                rid = params.get("review_id", "")
                if not rid:
                    return {"success": False, "error": "review_id required"}
                obj = add_defect(db, rid,
                    defect_type=params.get("defect_type", "factual"),
                    severity=params.get("severity", "minor"),
                    location=params.get("location"),
                    description=params.get("description"),
                    suggestion=params.get("suggestion"))
                return {"success": True, "defect_id": bytes_to_uuid_string(obj.id),
                    "defect_type": obj.defect_type, "severity": obj.severity}

            elif op == "update_verdict":
                rid = params.get("review_id", "")
                if not rid:
                    return {"success": False, "error": "review_id required"}
                obj = update_review_status(db, rid,
                    status=params.get("verdict", "approved"),
                    summary=params.get("summary"))
                if not obj:
                    return {"success": False, "error": "review not found"}
                return {"success": True, "review_id": bytes_to_uuid_string(obj.id),
                    "status": obj.status}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("quality_check error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()