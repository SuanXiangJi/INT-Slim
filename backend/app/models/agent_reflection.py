# -*- coding: utf-8 -*-
from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.mysql import BINARY, JSON

from app.models import Base


class AgentReflection(Base):
    __tablename__ = "agent_reflections"

    entry_id = Column(String(36), primary_key=True)
    user_id = Column(BINARY(16), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    entry_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    __table_args__ = (
        Index("idx_reflection_user_conversation", "user_id", "conversation_id"),
    )
