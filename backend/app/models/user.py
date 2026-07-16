from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.mysql import BINARY, TINYINT
from app.models import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(BINARY(16), primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(64))
    is_active = Column(TINYINT(1), default=1, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())