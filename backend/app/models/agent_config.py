from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base


class AgentConfig(Base):
    """每个用户的 Agent 配置"""
    __tablename__ = "agent_configs"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    default_model = Column(String(64), default="MiniMax-M2.7")
    sandbox_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
