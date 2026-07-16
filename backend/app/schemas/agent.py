"""
Agent 相关 Schema 定义
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any


class AgentConfigSchema(BaseModel):
    """Agent 配置 Schema"""
    user_id: str
    default_model: str
    sandbox_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SkillSchema(BaseModel):
    """Tool Schema"""
    id: str
    name: str
    description: str
    parameters_schema: Optional[Dict[str, Any]] = None
    is_builtin: bool = False
    enabled: bool = False


class SkillsResponse(BaseModel):
    """Tools 列表响应"""
    tools: List[SkillSchema]


class ToolsResponse(BaseModel):
    """Tools 列表响应（已启用的 tools）"""
    tools: List[Dict[str, Any]]


class SkillToggleRequest(BaseModel):
    """Tool 启用/禁用请求"""
    enabled: bool = True


class SandboxResponse(BaseModel):
    """沙盒信息响应"""
    exists: bool
    path: Optional[str] = None
