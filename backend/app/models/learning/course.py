# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, Integer, DateTime, func, JSON, Index
from app.models import Base

class Course(Base):
    __tablename__ = "courses"
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=False, default=0)
    category = Column(String(64), nullable=True, index=True)
    tags = Column(JSON, nullable=True)
    source = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    __table_args__ = (Index("idx_course_category", "category"),)
