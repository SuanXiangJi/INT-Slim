# -*- coding: utf-8 -*-
"""Content Assemble Tool - DB-backed content assembly."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.content import create_content, get_content, list_contents
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class ContentAssembleTool(BaseTool):
    """内容组装工具"""

    @property
    def id(self) -> str:
        return "content_assemble"

    @property
    def name(self) -> str:
        return "内容组装"

    @property
    def description(self) -> str:
        return (
            "将知识证据组装为结构化的教学内容。"
            "operation 支持: "
            "assemble(组装内容), get(获取已组装内容), list(列出已组装的内容)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["assemble", "get", "list"],
                    "description": "要执行的操作"
                },
                "plan_id": {"type": "string", "description": "学习计划ID"},
                "kp_id": {"type": "string", "description": "知识点ID"},
                "template_type": {
                    "type": "string",
                    "enum": ["lecture", "practice", "quiz", "summary", "example"],
                    "description": "内容模板类型"
                },
                "title": {"type": "string", "description": "内容标题"},
                "content_data": {
                    "type": "object",
                    "description": "组装的内容数据"
                },
                "content_id": {"type": "string", "description": "内容ID（用于 get）"}
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")

            if op == "assemble":
                obj = create_content(db,
                    template_type=params.get("template_type", "lecture"),
                    title=params.get("title", "Untitled"),
                    content_data=params.get("content_data", {}),
                    plan_id=params.get("plan_id"),
                    kp_id=params.get("kp_id"))
                return {"success": True, "content_id": bytes_to_uuid_string(obj.id),
                    "title": obj.title, "template_type": obj.template_type}

            elif op == "get":
                cid = params.get("content_id", "")
                if not cid:
                    return {"success": False, "error": "content_id required"}
                obj = get_content(db, cid)
                if not obj:
                    return {"success": False, "error": "content not found"}
                return {"success": True, "content_id": bytes_to_uuid_string(obj.id),
                    "title": obj.title, "template_type": obj.template_type,
                    "content_data": obj.content_data, "status": obj.status}

            elif op == "list":
                objs = list_contents(db, plan_id=params.get("plan_id"))
                contents = [{
                    "content_id": bytes_to_uuid_string(o.id),
                    "title": o.title,
                    "template_type": o.template_type,
                    "status": o.status
                } for o in objs]
                return {"success": True, "contents": contents, "total": len(contents)}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("content_assemble error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()