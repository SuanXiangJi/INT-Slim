from sqlalchemy import Column, String, Text, DateTime, func, Index, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.mysql import BINARY, ENUM
from app.models import Base


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(BINARY(16), primary_key=True)
    conversation_id = Column(BINARY(16), ForeignKey("conversations.id", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    role = Column(ENUM('user', 'assistant', 'tool', 'system', name='message_role'), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    is_favored = Column(Boolean, default=False, nullable=False, comment='是否收藏')
    
    # 可选：存储工具调用结果、元数据等（JSON）
    msg_metadata = Column(JSON, nullable=True, comment='e.g., tool_calls, model_name, token_usage')
    
    # Indexes
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_created_at", "created_at"),
    )