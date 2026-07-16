from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, func, JSON
from sqlalchemy.dialects.mysql import BINARY
from app.models import Base

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id = Column(BINARY(16), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    answers = Column(JSON, nullable=False, default=dict)
    score = Column(Float, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, server_default=func.current_timestamp())
