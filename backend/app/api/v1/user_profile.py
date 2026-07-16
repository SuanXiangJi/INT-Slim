"""
User profile API - per-user structured portrait CRUD + LLM analysis trigger.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models import get_db
from app.schemas.user import User as UserSchema
from app.dependencies.auth import get_current_user
from app.utils.uuid import uuid_string_to_bytes

from app.services.llm_service import llm_service
from app.services.user_profile import UserProfileService, UserProfile
from app.services.user_profile_db_store import DBProfileStore
from app.crud.message import get_messages_by_conversation_id
from app.crud.conversation import get_conversations_by_user_id
from app.schemas.user_profile import (
    UserProfileOut,
    UserProfileUpdate,
    ProfileAnalyzeRequest,
    ProfileContextResponse,
    ProfileResetResponse,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────


def _build_service(db: Session, user_id_bytes: bytes,
                    model: str = "deepseek:deepseek-chat") -> UserProfileService:
    store = DBProfileStore(db, user_id_bytes)
    return UserProfileService(store, llm_service=llm_service, model=model)


def _to_out(profile: UserProfile, include_context: bool = False) -> UserProfileOut:
    return UserProfileOut(
        user_id=profile.user_id,
        display_name=profile.display_name,
        profession=profile.profession,
        location=profile.location,
        language_preference=profile.language_preference,
        interests=list(profile.interests),
        expertise=dict(profile.expertise),
        preferences=dict(profile.preferences),
        topic_history=list(profile.topic_history),
        portrait_summary=profile.portrait_summary,
        portrait_updated_at=profile.portrait_updated_at,
        auto_update_enabled=profile.auto_update_enabled,
        analyzed_msg_count=profile.analyzed_msg_count,
        last_analyzed_at=profile.last_analyzed_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        context_string=profile.to_context_string() if include_context else None,
    )


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/profile", response_model=UserProfileOut)
def get_my_profile(
    include_context: bool = False,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get current user's profile. Set `include_context=true` to also
    return the prompt-injection context string (useful for debugging)."""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    svc = _build_service(db, user_id_bytes)
    profile = svc.get_or_create()
    return _to_out(profile, include_context=include_context)


@router.patch("/profile", response_model=UserProfileOut)
def update_my_profile(
    update: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Apply a partial manual update to the profile."""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    svc = _build_service(db, user_id_bytes)
    patch = update.dict(exclude_unset=True)
    profile = svc.update(patch)
    return _to_out(profile, include_context=False)


@router.post("/profile/analyze", response_model=UserProfileOut)
async def analyze_my_profile(
    req: ProfileAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Trigger LLM analysis on recent messages and merge into profile.

    - `message_count`: how many recent user/assistant messages to analyse (1-200)
    - `force=true`: bypass `auto_update_enabled` flag
    """
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    # Gather recent messages across user's conversations, newest first
    conversations = get_conversations_by_user_id(db, user_id_bytes)
    collected: List[dict] = []
    for conv in conversations:
        msgs = get_messages_by_conversation_id(db, conv.id)
        for m in msgs:
            if m.role in ("user", "assistant") and m.content:
                collected.append({"role": m.role, "content": m.content,
                                  "created_at": m.created_at})

    # Sort by created_at desc, take top N
    collected.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    recent = collected[: req.message_count]
    # Reverse so chronological for the prompt
    recent.reverse()

    svc = _build_service(db, user_id_bytes)
    profile = await svc.analyze_and_update(
        [{"role": m["role"], "content": m["content"]} for m in recent],
        force=req.force,
    )
    if profile is None:
        # Either disabled or failed - return current state
        profile = svc.get_or_create()
    return _to_out(profile, include_context=False)


@router.delete("/profile", response_model=ProfileResetResponse)
def reset_my_profile(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Wipe the profile back to defaults. Does NOT touch messages or conversations."""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    svc = _build_service(db, user_id_bytes)
    profile = svc.reset()
    return ProfileResetResponse(
        user_id=profile.user_id,
        message="Profile reset to defaults",
    )


@router.get("/profile/context", response_model=ProfileContextResponse)
def get_profile_context(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Return only the prompt-injection context string (for debugging)."""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    svc = _build_service(db, user_id_bytes)
    return ProfileContextResponse(
        user_id=user_id_bytes.hex(),
        context_string=svc.build_context_string(),
    )
