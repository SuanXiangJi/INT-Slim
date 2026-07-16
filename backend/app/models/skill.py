# -*- coding: utf-8 -*-
"""Agent Skill model - agent capabilities (distinct from learning knowledge points)."""
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.mysql import TINYINT, JSON
from app.models import Base

class Skill(Base):
    __tablename__ = "skills"
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    parameters_schema = Column(JSON, nullable=True)
    is_builtin = Column(TINYINT(1), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.current_timestamp())
