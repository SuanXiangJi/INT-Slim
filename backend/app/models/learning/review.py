# -*- coding: utf-8 -*-
"""Quality Review & Defect models."""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base

class QualityReview(Base):
    __tablename__ = "quality_reviews"
    id = Column(BINARY(16), primary_key=True)
    content_id = Column(String(64), nullable=False, index=True)
    reviewer_type = Column(ENUM("auto", "expert", "peer", name="reviewer_type"), nullable=False, default="auto")
    status = Column(ENUM("pending", "approved", "rejected", "needs_revision", name="review_status"), nullable=False, default="pending")
    risk_level = Column(ENUM("low", "medium", "high", name="risk_level"), nullable=False, default="medium")
    review_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_qr_content", "content_id"),)

class ReviewDefect(Base):
    __tablename__ = "review_defects"
    id = Column(BINARY(16), primary_key=True)
    review_id = Column(String(64), nullable=False, index=True)
    defect_type = Column(ENUM("factual", "normative", "adaptability", "clarity", name="defect_type"), nullable=False)
    severity = Column(ENUM("critical", "major", "minor", name="defect_severity"), nullable=False, default="minor")
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)