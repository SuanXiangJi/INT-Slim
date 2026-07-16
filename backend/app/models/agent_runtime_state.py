# -*- coding: utf-8 -*-
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.mysql import JSON

from app.models import Base


class AgentRuntimeState(Base):
    __tablename__ = "agent_runtime_states"

    conversation_id = Column(String(36), primary_key=True)
    status = Column(String(32), nullable=True, index=True)
    state_data = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
