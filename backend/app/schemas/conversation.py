from pydantic import BaseModel, Field
from datetime import datetime


class ConversationBase(BaseModel):
    title: str = Field("New Chat", min_length=1, max_length=200)


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation"""
    pass


class ConversationUpdate(ConversationBase):
    """Schema for updating a conversation"""
    pass


class Conversation(BaseModel):
    """Schema for returning conversation data"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True