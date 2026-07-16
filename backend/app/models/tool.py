from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.mysql import BINARY, TINYINT, JSON
from app.models import Base


class Tool(Base):
    """Tool 定义表"""
    __tablename__ = "tools"

    id = Column(String(64), primary_key=True)  # tool name as PK
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    parameters_schema = Column(JSON, nullable=True)  # OpenAI tool schema
    is_builtin = Column(TINYINT(1), default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
