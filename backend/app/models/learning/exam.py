# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, func, JSON, Index
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base

class Exam(Base):
    __tablename__ = "exams"
    id = Column(BINARY(16), primary_key=True)
    plan_id = Column(BINARY(16), ForeignKey("learning_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    id = Column(BINARY(16), primary_key=True)
    exam_id = Column(BINARY(16), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    kp_id = Column(String(64), nullable=True, index=True)
    question_type = Column(ENUM("choice", "fill_blank", "short_answer", "code", "true_false", name="qtype"), nullable=False)
    question_data = Column(JSON, nullable=False)
    difficulty = Column(Float, nullable=False, default=0.5)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_eq_exam_order", "exam_id", "sort_order"),)
