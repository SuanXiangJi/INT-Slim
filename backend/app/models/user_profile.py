"""
UserProfile SQLAlchemy model - persistent storage of user portraits.
"""
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, func, JSON, BigInteger, Index,
)
from sqlalchemy.dialects.mysql import BINARY, TINYINT

from app.models import Base


class UserProfile(Base):
    """用户画像 (per-user structured profile)."""
    __tablename__ = "user_profiles"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(
        BINARY(16),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Static / demographic
    display_name = Column(String(64), nullable=True)
    profession = Column(String(128), nullable=True)
    location = Column(String(128), nullable=True)
    language_preference = Column(String(16), nullable=True, default="zh-CN")

    # Dynamic / JSON
    interests = Column(JSON, nullable=True)
    expertise = Column(JSON, nullable=True)
    preferences = Column(JSON, nullable=True)
    topic_history = Column(JSON, nullable=True)

    # LLM-generated
    portrait_summary = Column(Text, nullable=True)
    portrait_updated_at = Column(DateTime, nullable=True)

    # Source / bookkeeping
    auto_update_enabled = Column(TINYINT(1), nullable=False, default=1)
    analyzed_msg_count = Column(BigInteger, nullable=False, default=0)
    last_analyzed_at = Column(DateTime, nullable=True)

    # Meta
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index("idx_user_profiles_user_id", "user_id"),
    )
