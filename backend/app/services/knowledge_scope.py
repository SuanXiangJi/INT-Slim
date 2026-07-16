"""Ownership helpers for private and shared knowledge-base documents."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session


SYSTEM_KB_USER_ID = b"\x00" * 16


def readable_owner_ids(user_id: bytes) -> tuple[bytes, ...]:
    if user_id == SYSTEM_KB_USER_ID:
        return (SYSTEM_KB_USER_ID,)
    return (user_id, SYSTEM_KB_USER_ID)


def knowledge_scope(owner_id: bytes, user_id: bytes) -> str:
    return "private" if owner_id == user_id else "public"


def resolve_document_owner(
    db: Session,
    user_id: bytes,
    doc_id: str,
) -> Optional[bytes]:
    """Resolve a readable document, preferring the user's private override."""
    from app.models.knowledge_base import KnowledgeDocument

    private = db.query(KnowledgeDocument.id).filter(
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.doc_id == doc_id,
    ).first()
    if private:
        return user_id
    public = db.query(KnowledgeDocument.id).filter(
        KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
        KnowledgeDocument.doc_id == doc_id,
    ).first()
    return SYSTEM_KB_USER_ID if public else None
