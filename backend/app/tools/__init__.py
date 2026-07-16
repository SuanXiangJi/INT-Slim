"""
内置 Tools 模块
导入时会自动注册 all tools
"""
from app.tools.base import tool_registry, BaseTool, register_tool

# 导入所有内置 tools
from app.tools import file_tool
from app.tools import code_exec_tool
from app.tools import web_search_tool
from app.tools import url_fetch_tool
from app.tools import datetime_tool
from app.tools import calculator_tool

# 导入学习平台 tools
from app.tools import learning  # noqa: F401

# 导出
__all__ = ["tool_registry", "BaseTool", "register_tool"]