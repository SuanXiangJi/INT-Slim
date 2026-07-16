"""
Tool 服务 - 管理 Tools 的注册、查询和执行
"""
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.tools.base import tool_registry, BaseTool
from app.models.tool import Tool
from app.models.agent_tool import AgentTool
from app.models.agent_config import AgentConfig


class ToolService:
    """Tool 服务"""

    def __init__(self):
        self._initialized = False

    def _ensure_initialized(self):
        """确保内置 tools 已注册"""
        if not self._initialized:
            # 触发 tools 模块导入，自动注册
            from app import tools  # noqa: F401
            self._initialized = True

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有已注册的 Tools"""
        self._ensure_initialized()
        return tool_registry.list_all()

    def get_tool(self, tool_id: str) -> Optional[BaseTool]:
        """获取指定 Tool"""
        self._ensure_initialized()
        return tool_registry.get(tool_id)

    def get_tool_definitions(self) -> List[dict]:
        """获取所有 Tools 的 tool 定义（用于 LLM）"""
        self._ensure_initialized()
        return tool_registry.get_tool_definitions()

    async def execute_tool(
        self,
        tool_id: str,
        params: dict,
        sandbox_path: str
    ) -> dict:
        """
        执行指定 Tool

        Args:
            tool_id: Tool ID
            params: Tool 参数
            sandbox_path: 用户沙盒路径

        Returns:
            Tool 执行结果
        """
        tool = self.get_tool(tool_id)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_id}' not found"}

        try:
            result = await tool.execute(params, sandbox_path)
            if isinstance(result, dict) and "success" not in result:
                result["success"] = not bool(result.get("error"))
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_builtin_tools_to_db(self, db: Session) -> int:
        """
        同步内置 Tools 到数据库
        Returns: 同步的 tool 数量
        """
        self._ensure_initialized()
        count = 0

        for tool_data in tool_registry.get_builtin_tools_data():
            # 检查是否已存在
            existing = db.query(Tool).filter(Tool.id == tool_data["id"]).first()
            if not existing:
                tool = Tool(**tool_data)
                db.add(tool)
                count += 1

        db.commit()
        return count

    def get_user_enabled_tools(self, db: Session, user_id: bytes) -> List[dict]:
        """
        获取用户已启用的 Tools 的 tool 定义
        如果用户没有配置过任何 tool，默认启用所有内置 tools
        """
        self._ensure_initialized()

        # 查询用户启用且在数据库中注册了的 tools
        enabled_agent_tools = (
            db.query(AgentTool)
            .filter(AgentTool.user_id == user_id, AgentTool.enabled == 1)
            .all()
        )

        enabled_tool_ids = {as_.tool_id for as_ in enabled_agent_tools}

        # 获取所有已注册的 tools
        all_tools = tool_registry.list_all()

        # 如果用户没有任何启用的 tool，默认启用所有内置 tools
        if not enabled_tool_ids:
            return [tool.get_tool_definition() for tool in all_tools]

        # Keep existing user configuration valid after the legacy tool rename.
        if "skill_graph" in enabled_tool_ids:
            enabled_tool_ids.add("knowledge_graph")

        # 返回用户启用且存在的 tools 的 tool 定义
        tool_defs = []
        for tool in all_tools:
            if tool.id in enabled_tool_ids:
                tool_defs.append(tool.get_tool_definition())

        return tool_defs

    def enable_tool_for_user(self, db: Session, user_id: bytes, tool_id: str) -> bool:
        """
        为用户启用指定 Tool
        如果 agent_tool 记录不存在则创建
        """
        self._ensure_initialized()

        # 检查 tool 是否存在
        tool = self.get_tool(tool_id)
        if not tool:
            return False

        # 查找或创建 agent_tool 记录
        agent_tool = (
            db.query(AgentTool)
            .filter(AgentTool.user_id == user_id, AgentTool.tool_id == tool_id)
            .first()
        )

        if agent_tool:
            agent_tool.enabled = 1
        else:
            import uuid
            agent_tool = AgentTool(
                id=uuid.uuid4().bytes,
                user_id=user_id,
                tool_id=tool_id,
                enabled=1
            )
            db.add(agent_tool)

        db.commit()
        return True

    def disable_tool_for_user(self, db: Session, user_id: bytes, tool_id: str) -> bool:
        """
        为用户禁用指定 Tool
        """
        agent_tool = (
            db.query(AgentTool)
            .filter(AgentTool.user_id == user_id, AgentTool.tool_id == tool_id)
            .first()
        )

        if agent_tool:
            agent_tool.enabled = 0
            db.commit()
            return True
        return False

    def get_all_tools_with_status(self, db: Session, user_id: bytes) -> List[dict]:
        """
        获取所有 Tools 及其在指定用户处的启用状态
        """
        self._ensure_initialized()

        # 获取用户启用状态
        enabled_agent_tools = (
            db.query(AgentTool)
            .filter(AgentTool.user_id == user_id, AgentTool.enabled == 1)
            .all()
        )
        enabled_tool_ids = {as_.tool_id for as_ in enabled_agent_tools}

        # 构建结果
        result = []
        for tool in tool_registry.list_all():
            result.append({
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
                "is_builtin": True,
                "enabled": tool.id in enabled_tool_ids
            })

        return result


# 全局单例
tool_service = ToolService()
