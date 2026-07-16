# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, func, JSON, Index, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import BINARY
from app.models import Base

class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, index=True)
    category = Column(String(64), nullable=True, index=True)
    description = Column(Text, nullable=True)
    difficulty = Column(Float, nullable=False, default=0.5)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_kp_category", "category"),)

class KpPrerequisite(Base):
    __tablename__ = "kp_prerequisites"
    kp_id = Column(String(64), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_kp_id = Column(String(64), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (PrimaryKeyConstraint("kp_id", "prerequisite_kp_id", name="pk_kp_prereq"),)

class StudyEvent(Base):
    __tablename__ = "study_events"
    id = Column(String(64), primary_key=True)
    user_id = Column(BINARY(16), nullable=False, index=True)
    kp_id = Column(String(64), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    studied_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_study_user_kp", "user_id", "kp_id"),)

