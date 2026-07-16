# -*- coding: utf-8 -*-
"""Agent-Skill association model."""
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base

class AgentSkill(Base):
    __tablename__ = "agent_skills"
    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id"), nullable=False, index=True)
    skill_id = Column(String(64), ForeignKey("skills.id"), nullable=False, index=True)
    enabled = Column(TINYINT(1), nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("ix_agent_skills_user_skill", "user_id", "skill_id", unique=True),)
