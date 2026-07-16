# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base


class LearningTask(Base):
    """A learner-owned, actionable study item."""
    __tablename__ = "learning_tasks"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(32), nullable=False, default="study")
    kp_id = Column(String(64), nullable=True, index=True)
    due_date = Column(DateTime, nullable=True, index=True)
    status = Column(ENUM("todo", "done", name="learning_task_status"), nullable=False, default="todo", index=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (Index("idx_learning_task_user_status", "user_id", "status"),)
