# -*- coding: utf-8 -*-
"""Candidate Rank Tool - DB-backed candidate ranking and scoring."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.candidate import create_candidate, list_candidates, select_candidate
from app.utils.uuid import bytes_to_uuid_string

logger = logging.getLogger(__name__)


@register_tool
class CandidateRankTool(BaseTool):
    """候选排序工具"""

    @property
    def id(self) -> str:
        return "candidate_rank"

    @property
    def name(self) -> str:
        return "候选排序"

    @property
    def description(self) -> str:
        return (
            "对多个候选方案/内容进行打分排序，输出排名与风险评估。"
            "operation 支持: "
            "create_ranking(创建排序任务), submit_score(提交评分), "
            "get_result(获取结果), list(列出排序记录), "
            "select(选择最终方案)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create_ranking", "submit_score", "get_result", "list", "select"],
                    "description": "要执行的操作"
                },
                "content_id": {"type": "string", "description": "内容ID"},
                "candidate_id": {"type": "string", "description": "候选ID"},
                "rank_score": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.0},
                "risk_info": {"type": "object", "description": "风险信息"}
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")

            if op == "create_ranking" or op == "submit_score":
                obj = create_candidate(db,
                    content_id=params.get("content_id", ""),
                    rank_score=params.get("rank_score", 0.0),
                    risk_info=params.get("risk_info", {}))
                return {"success": True, "candidate_id": bytes_to_uuid_string(obj.id),
                    "rank_score": obj.rank_score}

            elif op == "get_result" or op == "list":
                rows = list_candidates(db, content_id=params.get("content_id"))
                rankings = [{
                    "candidate_id": bytes_to_uuid_string(r.id),
                    "content_id": r.content_id,
                    "rank_score": r.rank_score,
                    "is_selected": bool(r.is_selected),
                    "risk_info": r.risk_info
                } for r in rows]
                return {"success": True, "rankings": rankings, "total": len(rankings)}

            elif op == "select":
                obj = select_candidate(db, candidate_id=params.get("candidate_id", ""))
                if not obj:
                    return {"success": False, "error": "candidate not found"}
                return {"success": True, "candidate_id": bytes_to_uuid_string(obj.id),
                    "is_selected": True}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("candidate_rank error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()