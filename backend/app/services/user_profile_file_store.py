"""
FileProfileStore - persists UserProfile to a local JSON file.

Default path: ~/.xbots/<os_username>/profile.json
Override: XBOTS_PROFILE_DIR env var, or pass base_dir explicitly.

Designed for CLI usage where each host user has exactly one profile.
"""
from __future__ import annotations

import io
import json
import logging
import os
from typing import Optional

from app.services.user_profile import (
    UserProfile,
    ProfileStore,
    get_default_user_id,
)


DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), ".xbots")
DEFAULT_FILENAME = "profile.json"


class FileProfileStore(ProfileStore):
    """JSON-file backed profile store."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        base_dir: Optional[str] = None,
        filename: str = DEFAULT_FILENAME,
    ):
        self._user_id = user_id or get_default_user_id()
        env_dir = os.environ.get("XBOTS_PROFILE_DIR")
        self._base_dir = base_dir or env_dir or DEFAULT_BASE_DIR
        self._filename = filename
        self._path = os.path.join(self._base_dir, self._user_id, filename)

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def path(self) -> str:
        return self._path

    @property
    def base_dir(self) -> str:
        return self._base_dir

    def load(self) -> Optional[UserProfile]:
        if not os.path.exists(self._path):
            return None
        try:
            with io.open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure user_id matches the store owner
            data["user_id"] = self._user_id
            return UserProfile.from_dict(data)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logging.warning(f"Could not load profile at {self._path}: {e}")
            return None

    def save(self, profile: UserProfile) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        # Atomic-ish write: write to temp file, then rename
        tmp = self._path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, self._path)

    def delete(self) -> None:
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except OSError as e:
            logging.warning(f"Could not delete profile at {self._path}: {e}")

    def __repr__(self) -> str:
        return f"FileProfileStore(user_id={self._user_id!r}, path={self._path!r})"
