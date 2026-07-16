# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, JSON, Index
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base

class ContentAssembly(Base):
    __tablename__ = "content_assemblies"
    id = Column(BINARY(16), primary_key=True)
    plan_id = Column(BINARY(16), ForeignKey("learning_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    kp_id = Column(String(64), nullable=True, index=True)
    template_type = Column(ENUM("lecture", "practice", "quiz", "summary", "example", name="ca_template"), nullable=False)
    title = Column(String(255), nullable=False)
    content_data = Column(JSON, nullable=False)
    status = Column(ENUM("draft", "review", "published", "rejected", name="ca_status"), nullable=False, default="draft")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    __table_args__ = (Index("idx_ca_plan_status", "plan_id", "status"),)
