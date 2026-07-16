# -*- coding: utf-8 -*-
"""Question Gen Tool - DB-backed exam and question management."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.exam import create_exam, get_exam, list_exams, add_question, list_questions
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class QuestionGenTool(BaseTool):
    """试题生成工具"""

    @property
    def id(self) -> str:
        return "question_gen"

    @property
    def name(self) -> str:
        return "试题生成"

    @property
    def description(self) -> str:
        return (
            "生成测试题。创建试卷模板，录入题目，查询已有题目。"
            "operation 支持: "
            "create_exam(创建试卷), add_question(添加试题), "
            "get_exam(查看试卷), list_exams(列出试卷), "
            "list_questions(列试题)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create_exam", "add_question", "get_exam",
                             "list_exams", "list_questions"],
                    "description": "要执行的操作"
                },
                "title": {"type": "string", "description": "试卷标题"},
                "exam_id": {"type": "string", "description": "试卷ID"},
                "plan_id": {"type": "string", "description": "关联学习计划ID"},
                "description": {"type": "string", "description": "试卷描述"},
                "kp_id": {"type": "string", "description": "关联知识点ID"},
                "qtype": {"type": "string", "enum": ["choice", "fill_blank",
                    "short_answer", "code", "true_false"],
                    "description": "题目类型"},
                "question_data": {"type": "object", "description": "题目内容"},
                "difficulty": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5}
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")

            if op == "create_exam":
                obj = create_exam(db,
                    title=params.get("title", "New Exam"),
                    plan_id=params.get("plan_id"),
                    description=params.get("description"))
                return {"success": True, "exam_id": bytes_to_uuid_string(obj.id),
                    "title": obj.title}

            elif op == "add_question":
                obj = add_question(db,
                    exam_id=params.get("exam_id", ""),
                    kp_id=params.get("kp_id", ""),
                    qtype=params.get("qtype", "choice"),
                    question_data=params.get("question_data", {}),
                    difficulty=params.get("difficulty", 0.5))
                return {"success": True, "question_id": bytes_to_uuid_string(obj.id),
                    "qtype": obj.question_type}

            elif op == "get_exam":
                eid = params.get("exam_id", "")
                obj = get_exam(db, eid)
                if not obj:
                    return {"success": False, "error": "exam not found"}
                qs = list_questions(db, eid)
                return {"success": True, "exam_id": bytes_to_uuid_string(obj.id),
                    "title": obj.title,
                    "questions": [{"id": bytes_to_uuid_string(q.id),
                        "kp_id": q.kp_id, "qtype": q.question_type,
                        "difficulty": q.difficulty} for q in qs],
                    "question_count": len(qs)}

            elif op == "list_exams":
                objs = list_exams(db, plan_id=params.get("plan_id"))
                exams = [{
                    "exam_id": bytes_to_uuid_string(o.id),
                    "title": o.title,
                    "created_at": o.created_at.isoformat() if o.created_at else ""
                } for o in objs]
                return {"success": True, "exams": exams, "total": len(exams)}

            elif op == "list_questions":
                qs = list_questions(db, exam_id=params.get("exam_id", ""))
                questions = [{
                    "id": bytes_to_uuid_string(q.id),
                    "kp_id": q.kp_id, "qtype": q.question_type,
                    "difficulty": q.difficulty
                } for q in qs]
                return {"success": True, "questions": questions, "total": len(questions)}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("question_gen error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()