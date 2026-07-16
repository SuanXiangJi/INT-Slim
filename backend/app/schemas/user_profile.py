"""
Pydantic schemas for user profile API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    """Partial update payload - all fields optional."""
    display_name: Optional[str] = Field(None, max_length=64)
    profession: Optional[str] = Field(None, max_length=128)
    location: Optional[str] = Field(None, max_length=128)
    language_preference: Optional[str] = Field(None, max_length=16)
    interests: Optional[List[str]] = None
    expertise: Optional[Dict[str, str]] = None
    preferences: Optional[Dict[str, Any]] = None
    topic_history: Optional[List[Dict[str, Any]]] = None
    portrait_summary: Optional[str] = None
    auto_update_enabled: Optional[bool] = None


class UserProfileOut(BaseModel):
    user_id: str
    display_name: str = ""
    profession: str = ""
    location: str = ""
    language_preference: str = "zh-CN"
    interests: List[str] = []
    expertise: Dict[str, str] = {}
    preferences: Dict[str, Any] = {}
    topic_history: List[Dict[str, Any]] = []
    portrait_summary: str = ""
    portrait_updated_at: Optional[str] = None
    auto_update_enabled: bool = True
    analyzed_msg_count: int = 0
    last_analyzed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    context_string: Optional[str] = None


class ProfileAnalyzeRequest(BaseModel):
    """Trigger LLM-based profile analysis."""
    force: bool = False
    message_count: int = Field(20, ge=1, le=200)


class ProfileContextResponse(BaseModel):
    """The compact context string injected into the system prompt."""
    user_id: str
    context_string: str


class ProfileResetResponse(BaseModel):
    user_id: str
    message: str
