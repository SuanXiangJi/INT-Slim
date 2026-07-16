"""
Agent 配置服务 - 仅负责 Agent 配置（默认模型等）的持久化。

实际的对话 / 工具调用循环已迁移到 app.services.autonomous_agent。
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.agent_config import AgentConfig


class AgentService:
    """只负责 Agent 配置（default_model 等）的 CRUD。"""

    # ── Agent config ────────────────────────────────────────────────
    def get_agent_config_sync(self, db: Session, user_id: bytes) -> Optional[dict]:
        config = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        if not config:
            return None
        return {
            "user_id": config.user_id.hex(),
            "default_model": config.default_model,
            "sandbox_path": config.sandbox_path,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    def update_agent_config_sync(
        self,
        db: Session,
        user_id: bytes,
        default_model: Optional[str] = None,
    ) -> AgentConfig:
        config = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        if not config:
            import uuid
            config = AgentConfig(
                id=uuid.uuid4().bytes,
                user_id=user_id,
                default_model=default_model or "deepseek-v4-pro",
            )
            db.add(config)
        else:
            if default_model is not None:
                config.default_model = default_model
        db.commit()
        db.refresh(config)
        return config


# 全局单例
agent_service = AgentService()