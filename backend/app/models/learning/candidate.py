# -*- coding: utf-8 -*-
"""Candidate Ranking model."""
from sqlalchemy import Column, Float, String, DateTime, ForeignKey, func, JSON
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base

class CandidateRanking(Base):
    __tablename__ = "candidate_rankings"
    id = Column(BINARY(16), primary_key=True)
    content_id = Column(String(64), nullable=False, index=True)
    rank_score = Column(Float, nullable=False, default=0.0)
    risk_info = Column(JSON, nullable=True)
    is_selected = Column(TINYINT(1), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.current_timestamp())