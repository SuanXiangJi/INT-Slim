# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func, JSON, Index
from sqlalchemy.dialects.mysql import BINARY
from app.models import Base

class Learner(Base):
    __tablename__ = "learners"
    id = Column(BINARY(16), primary_key=True)
    name = Column(String(64), nullable=False)
    grade = Column(String(64), nullable=True)
    language = Column(String(16), nullable=False, default="zh-CN")
    goals = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (Index("idx_learners_name", "name"),)

class LearnerMastery(Base):
    __tablename__ = "learner_mastery"
    id = Column(BINARY(16), primary_key=True)
    learner_id = Column(BINARY(16), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    kp_id = Column(String(64), nullable=False, index=True)
    level = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.5)
    last_assessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_lm_learner_kp", "learner_id", "kp_id", unique=True),)

class LearnerError(Base):
    __tablename__ = "learner_errors"
    id = Column(BINARY(16), primary_key=True)
    learner_id = Column(BINARY(16), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    kp_id = Column(String(64), nullable=True, index=True)
    error_type = Column(String(64), nullable=False)
    count = Column(Float, nullable=False, default=1)
    last_occurrence = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_le_learner_type", "learner_id", "error_type"),)

class LearnerCognitiveLoad(Base):
    __tablename__ = "learner_cognitive_load"
    id = Column(BINARY(16), primary_key=True)
    learner_id = Column(BINARY(16), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    current_load = Column(Float, nullable=False, default=0.0)
    threshold = Column(Float, nullable=False, default=0.8)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
