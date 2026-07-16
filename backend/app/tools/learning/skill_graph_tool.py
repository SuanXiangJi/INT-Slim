# -*- coding: utf-8 -*-
"""Knowledge Graph Tool - DB-backed knowledge points and prerequisites."""
import logging
from typing import Any
from app.tools.base import BaseTool, register_tool
from app.crud.learning.knowledge_point import (
    create_kp, get_kp, list_kps, search_kps,
    add_prerequisite, get_prerequisites, get_next_kps, find_learning_path
)

logger = logging.getLogger(__name__)


@register_tool
class KnowledgeGraphTool(BaseTool):
    """知识点图谱工具。This is a Tool, not an Agent Skill."""

    @property
    def id(self) -> str:
        return "knowledge_graph"

    @property
    def name(self) -> str:
        return "知识点图谱"

    @property
    def description(self) -> str:
        return (
            "管理知识点及其先修关系。这是工具，不是 Agent Skill。operation 支持: "
            "list_knowledge_points(列出知识点), get_knowledge_point(查看详情), "
            "find_path(找学习路径), add_knowledge_point(添加知识点), "
            "get_prerequisites(获取前置知识点), get_next_points(获取进阶知识点), "
            "search(搜索知识点)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list_knowledge_points", "get_knowledge_point", "find_path",
                             "add_knowledge_point", "get_prerequisites", "get_next_points", "search"],
                    "description": "要执行的操作"
                },
                "knowledge_point_id": {
                    "type": "string",
                    "description": "知识点ID"
                },
                "target_knowledge_point": {
                    "type": "string",
                    "description": "目标知识点（用于 find_path）"
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（用于 search）"
                },
                "knowledge_point_data": {
                    "type": "object",
                    "description": "知识点数据（用于 add_knowledge_point）",
                    "properties": {
                        "name": {"type": "string"},
                        "category": {"type": "string"},
                        "description": {"type": "string"},
                        "difficulty": {"type": "number", "minimum": 0, "maximum": 1},
                        "prerequisites": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "category": {
                    "type": "string",
                    "description": "按类别过滤"
                }
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        from app.models import SessionLocal
        db = SessionLocal()
        try:
            op = params.get("operation", "")
            op = {
                "list_skills": "list_knowledge_points",
                "get_skill": "get_knowledge_point",
                "add_skill": "add_knowledge_point",
                "get_next_skills": "get_next_points",
            }.get(op, op)

            if op == "list_knowledge_points":
                points = list_kps(db, params.get("category"))
                return {
                    "success": True,
                    "knowledge_points": [{"id": s.id, "name": s.name,
                                "category": s.category,
                                "difficulty": s.difficulty}
                               for s in points],
                    "total": len(points)
                }

            elif op == "get_knowledge_point":
                sid = params.get("knowledge_point_id") or params.get("skill_id", "")
                s = get_kp(db, sid)
                if not s:
                    return {"success": False, "error": f"knowledge point {sid} not found"}
                return {"success": True, "knowledge_point": {
                    "id": s.id, "name": s.name,
                    "category": s.category,
                    "description": s.description,
                    "difficulty": s.difficulty,
                    "tags": s.tags
                }}

            elif op == "search":
                query = params.get("query", "")
                if not query:
                    return {"success": False, "error": "query required"}
                points = search_kps(db, query)
                return {
                    "success": True,
                    "knowledge_points": [{"id": s.id, "name": s.name,
                                "category": s.category,
                                "description": (s.description or "")[:100]}
                               for s in points],
                    "total": len(points)
                }

            elif op == "find_path":
                target = params.get("target_knowledge_point") or params.get("target_skill", "")
                path = find_learning_path(db, target)
                if not path:
                    return {"success": False, "error": f"target knowledge point '{target}' not found"}
                return {
                    "success": True, "target": target,
                    "path_points": [{"id": s.id, "name": s.name} for s in path if s],
                    "path_ids": [s.id for s in path if s],
                    "steps": len([s for s in path if s])
                }

            elif op == "add_knowledge_point":
                sd = params.get("knowledge_point_data") or params.get("skill_data", {})
                s = create_kp(db,
                    name=sd.get("name", ""),
                    category=sd.get("category"),
                    description=sd.get("description"),
                    difficulty=sd.get("difficulty", 0.5))
                prereqs = sd.get("prerequisites", [])
                for pid in prereqs:
                    try:
                        add_prerequisite(db, s.id, pid)
                    except Exception:
                        pass  # skip invalid prereqs
                return {"success": True, "knowledge_point": {
                    "id": s.id, "name": s.name,
                    "category": s.category,
                    "description": s.description,
                    "difficulty": s.difficulty
                }}

            elif op == "get_prerequisites":
                sid = params.get("knowledge_point_id") or params.get("skill_id", "")
                prereqs = get_prerequisites(db, sid)
                nexts = get_next_kps(db, sid)
                return {"success": True, "knowledge_point_id": sid,
                    "prerequisites": [{"id": p.id, "name": p.name} for p in prereqs if p],
                    "next_points": [{"id": p.id, "name": p.name} for p in nexts if p]}

            elif op == "get_next_points":
                sid = params.get("knowledge_point_id") or params.get("skill_id", "")
                nexts = get_next_kps(db, sid)
                return {"success": True, "knowledge_point_id": sid,
                    "next_points": [{"id": p.id, "name": p.name} for p in nexts if p],
                    "count": len(nexts)}

            else:
                return {"success": False, "error": f"Unknown operation: {op}"}

        except Exception as e:
            logger.error("knowledge_graph error", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            db.close()
