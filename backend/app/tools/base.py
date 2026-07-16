"""
Tool 基类和注册机制
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import inspect


class BaseTool(ABC):
    """Tool 抽象基类"""

    @property
    @abstractmethod
    def id(self) -> str:
        """Tool 唯一标识符"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool 显示名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool 描述，用于 LLM 理解何时使用此 Tool"""
        pass

    @property
    def parameters_schema(self) -> Optional[dict]:
        """
        返回 OpenAI tool schema
        如果返回 None，则此 tool 不需要参数
        """
        return None

    @abstractmethod
    async def execute(self, params: dict, sandbox_path: str) -> Any:
        """
        执行 Tool

        Args:
            params: LLM 传递的参数
            sandbox_path: 用户沙盒路径

        Returns:
            执行结果（会被 JSON 序列化后发送给 LLM）
        """
        pass

    def get_tool_definition(self) -> dict:
        """
        获取 OpenAI tool 定义
        """
        schema = self.parameters_schema
        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self.description,
                "parameters": schema if schema else {"type": "object", "properties": {}}
            }
        }


class ToolRegistry:
    """Tool 注册表"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个 Tool"""
        if tool.id in self._tools:
            raise ValueError(f"Tool with id '{tool.id}' already registered")
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Optional[BaseTool]:
        """获取 Tool"""
        return self._tools.get(tool_id)

    def list_all(self) -> List[BaseTool]:
        """列出所有已注册的 Tools"""
        return list(self._tools.values())

    def get_tool_definitions(self) -> List[dict]:
        """获取所有 Tools 的 tool 定义"""
        return [tool.get_tool_definition() for tool in self._tools.values()]

    def get_builtin_tools_data(self) -> List[dict]:
        """获取内置 Tools 的数据库格式数据"""
        return [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
                "is_builtin": True
            }
            for tool in self._tools.values()
        ]


# 全局注册表
tool_registry = ToolRegistry()


def register_tool(tool_class):
    """
    Tool 注册装饰器
    使用方式：
        @register_tool
        class MyTool(BaseTool):
            ...
    """
    tool_instance = tool_class()
    tool_registry.register(tool_instance)
    return tool_class
