from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional, Dict, Any


class MessageBase(BaseModel):
    content: str = Field(..., min_length=0, max_length=100000)


class MessageCreate(MessageBase):
    """Schema for creating a new message"""
    model: Optional[str] = None  # Optional model override
    enable_agent: bool = False  # Enable Agent mode with tool calling
    reconnect: bool = False  # Reconnect to running agent (skip restart)

    @model_validator(mode='before')
    @classmethod
    def check_content(cls, data: Any) -> Any:
        """Allow empty content when reconnecting to a running agent."""
        if isinstance(data, dict):
            reconnect = data.get('reconnect', False)
            content = data.get('content', '')
            if reconnect and not content:
                data['content'] = '__reconnect__'
            elif not content:
                raise ValueError('Content must not be empty')
        return data


class Message(BaseModel):
    """Schema for returning message data"""
    id: str
    conversation_id: str
    role: str  # user, assistant, tool, system
    content: str
    created_at: datetime
    is_favored: bool = False
    metadata: Optional[Dict[str, Any]] = None  # For tool messages: tool_call_id, tool_name

    class Config:
        from_attributes = True


class MessageFavorUpdate(BaseModel):
    """Schema for updating message favor status"""
    is_favored: bool
