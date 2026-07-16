# -*- coding: utf-8 -*-
"""Project model."""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.mysql import BINARY
from app.models import Base

class Project(Base):
    __tablename__ = "projects"
    id = Column(BINARY(16), primary_key=True)
    owner_id = Column(BINARY(16), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
