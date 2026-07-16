"""
Agent API 路由 - 管理 Agent 配置和 Tools
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.models import get_db
from app.schemas.user import User as UserSchema
from app.dependencies.auth import get_current_user
from app.utils.uuid import uuid_string_to_bytes, bytes_to_uuid_string
from app.services.agent_service import agent_service
from app.services.tool_service import tool_service
from app.services.sandbox_service import sandbox_service

router = APIRouter()


@router.get("/config")
def get_agent_config(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """获取当前用户的 Agent 配置"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    config = agent_service.get_agent_config_sync(db, user_id_bytes)
    if not config:
        # 返回默认配置
        return {
            "user_id": current_user.id,
            "default_model": "deepseek-v4-pro",
            "sandbox_path": None,
            "created_at": None,
            "updated_at": None
        }

    return config


@router.put("/config")
def update_agent_config_endpoint(
    default_model: str = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """更新 Agent 配置"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    config = agent_service.update_agent_config_sync(db, user_id_bytes, default_model)

    return {
        "user_id": bytes_to_uuid_string(config.user_id),
        "default_model": config.default_model,
        "sandbox_path": config.sandbox_path,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None
    }


@router.get("/tools")
def get_all_tools(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """获取所有可用的 Tools 及其启用状态"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    tools = tool_service.get_all_tools_with_status(db, user_id_bytes)
    return {"tools": tools}


@router.get("/tools/enabled")
def get_enabled_tools(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """获取当前用户已启用的 Tools"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    tools = tool_service.get_user_enabled_tools(db, user_id_bytes)
    return {"tools": tools}


@router.put("/tools/{tool_id}")
def toggle_tool(
    tool_id: str,
    enabled: bool = True,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """启用或禁用指定 Tool"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    if enabled:
        success = tool_service.enable_tool_for_user(db, user_id_bytes, tool_id)
    else:
        success = tool_service.disable_tool_for_user(db, user_id_bytes, tool_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found"
        )

    return {"tool_id": tool_id, "enabled": enabled}


@router.post("/tools/sync")
def sync_builtin_tools(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """同步内置 Tools 到数据库"""
    count = tool_service.sync_builtin_tools_to_db(db)
    return {"synced_count": count}


@router.post("/sandbox/init")
def init_sandbox(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """为当前用户初始化沙盒"""
    import asyncio
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    async def _init():
        return await sandbox_service.create_sandbox(user_id_bytes)

    # 由于 FastAPI 是异步的，我们需要处理同步调用
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在事件循环中，创建 task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _init())
                sandbox_path = future.result()
        else:
            sandbox_path = loop.run_until_complete(_init())
    except RuntimeError:
        # 没有事件循环，直接运行
        sandbox_path = asyncio.run(_init())

    return {"sandbox_path": sandbox_path}


@router.get("/sandbox")
def get_sandbox_info(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """获取当前用户的沙盒信息"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    sandbox_path = sandbox_service.get_sandbox_path(user_id_bytes)
    if not sandbox_path:
        return {"exists": False, "path": None}

    return {
        "exists": True,
        "path": sandbox_path
    }
