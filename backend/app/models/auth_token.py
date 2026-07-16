from sqlalchemy import Column, String, DateTime, func, Index, ForeignKey, Text
from sqlalchemy.dialects.mysql import BINARY, TINYINT, BIGINT
from app.models import Base


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    token_type = Column(String(20), nullable=False, default="access_token")
    created_at = Column(DateTime, server_default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(TINYINT(1), nullable=False, default=0)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_name = Column(String(100))

    # Indexes
    __table_args__ = (
        Index("idx_auth_tokens_user_id", "user_id"),
        Index("idx_auth_tokens_expires_at", "expires_at"),
    )