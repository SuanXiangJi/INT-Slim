from sqlalchemy import Column, String, DateTime, func, Index, ForeignKey
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Chat")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    is_deleted = Column(TINYINT(1), nullable=False, default=0)

    # Indexes
    __table_args__ = (
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_updated_at", "updated_at"),
    )