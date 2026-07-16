# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base

class LearningPlan(Base):
    __tablename__ = "learning_plans"
    id = Column(BINARY(16), primary_key=True)
    learner_id = Column(BINARY(16), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    goal = Column(Text, nullable=True)
    status = Column(ENUM("draft", "active", "completed", "paused", name="plan_status"), nullable=False, default="draft")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (Index("idx_lp_learner_status", "learner_id", "status"),)

class PlanKnowledgePoint(Base):
    __tablename__ = "plan_knowledge_points"
    id = Column(BINARY(16), primary_key=True)
    plan_id = Column(BINARY(16), ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    kp_id = Column(String(64), nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(ENUM("pending", "learning", "completed", "skipped", name="pkp_status"), nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_pkp_plan_order", "plan_id", "sort_order"),)
