"""
DBProfileStore - persists UserProfile to user_profiles table (web backend).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile as UserProfileRow
from app.services.user_profile import UserProfile as UserProfileDTO, ProfileStore


class DBProfileStore(ProfileStore):
    """SQLAlchemy-backed profile store."""

    def __init__(self, db: Session, user_id_bytes: bytes):
        self.db = db
        self._user_id_bytes = user_id_bytes

    @property
    def user_id(self) -> str:
        return self._user_id_bytes.hex()

    def load(self) -> Optional[UserProfileDTO]:
        row = (
            self.db.query(UserProfileRow)
            .filter(UserProfileRow.user_id == self._user_id_bytes)
            .first()
        )
        if row is None:
            return None
        return _row_to_dto(row)

    def save(self, profile: UserProfileDTO) -> None:
        row = (
            self.db.query(UserProfileRow)
            .filter(UserProfileRow.user_id == self._user_id_bytes)
            .first()
        )
        if row is None:
            from app.utils.uuid import generate_uuid
            row = UserProfileRow(
                id=generate_uuid(),
                user_id=self._user_id_bytes,
            )
            self.db.add(row)
        _dto_to_row(profile, row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def delete(self) -> None:
        row = (
            self.db.query(UserProfileRow)
            .filter(UserProfileRow.user_id == self._user_id_bytes)
            .first()
        )
        if row is not None:
            self.db.delete(row)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_iso(value: Optional[str]):
    if not value:
        return None
    try:
        s = str(value).rstrip("Z")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _row_to_dto(row: UserProfileRow) -> UserProfileDTO:
    return UserProfileDTO(
        user_id=row.user_id.hex() if row.user_id else "",
        display_name=row.display_name or "",
        profession=row.profession or "",
        location=row.location or "",
        language_preference=row.language_preference or "zh-CN",
        interests=list(row.interests or []),
        expertise=dict(row.expertise or {}),
        preferences=dict(row.preferences or {}),
        topic_history=list(row.topic_history or []),
        portrait_summary=row.portrait_summary or "",
        portrait_updated_at=_iso(row.portrait_updated_at),
        auto_update_enabled=bool(row.auto_update_enabled),
        analyzed_msg_count=int(row.analyzed_msg_count or 0),
        last_analyzed_at=_iso(row.last_analyzed_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _dto_to_row(dto: UserProfileDTO, row: UserProfileRow) -> None:
    row.display_name = dto.display_name or None
    row.profession = dto.profession or None
    row.location = dto.location or None
    row.language_preference = dto.language_preference or "zh-CN"
    row.interests = list(dto.interests) if dto.interests else None
    row.expertise = dict(dto.expertise) if dto.expertise else None
    row.preferences = dict(dto.preferences) if dto.preferences else None
    row.topic_history = list(dto.topic_history) if dto.topic_history else None
    row.portrait_summary = dto.portrait_summary or None
    row.portrait_updated_at = _parse_iso(dto.portrait_updated_at)
    row.auto_update_enabled = 1 if dto.auto_update_enabled else 0
    row.analyzed_msg_count = int(dto.analyzed_msg_count or 0)
    row.last_analyzed_at = _parse_iso(dto.last_analyzed_at)
