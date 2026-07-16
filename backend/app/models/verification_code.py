from sqlalchemy import Column, String, Boolean, DateTime, Enum, func
from sqlalchemy.dialects.mysql import BINARY, TINYINT, CHAR
from app.models import Base


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    
    id = Column(BINARY(16), primary_key=True, index=True)
    user_id = Column(BINARY(16), index=True, nullable=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(CHAR(6), nullable=False)
    purpose = Column(Enum('register', 'login', 'reset_password'), nullable=False, index=True)
    is_used = Column(TINYINT(1), default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # 复合索引
    __table_args__ = (
        # Index('idx_email_purpose', 'email', 'purpose'),
    )