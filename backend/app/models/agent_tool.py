from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base


class AgentTool(Base):
    """Agent 与 Tool 的关联（启用/禁用）"""
    __tablename__ = "agent_tools"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id"), nullable=False, index=True)
    tool_id = Column(String(64), ForeignKey("tools.id"), nullable=False, index=True)
    enabled = Column(TINYINT(1), default=1, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
