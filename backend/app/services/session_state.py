# -*- coding: utf-8 -*-
"""Session State Service - persists agent state for interrupt/resume."""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# State storage root
STATE_ROOT = Path(__file__).parent.parent.parent / "sandbox" / "session_states"


class SessionState:
    """Persistent state for a conversation session."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.state_dir = STATE_ROOT / conversation_id[:16]
        self.state_file = self.state_dir / "state.json"
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            from app.models import SessionLocal
            from app.models.agent_runtime_state import AgentRuntimeState
            with SessionLocal() as db:
                row = db.get(AgentRuntimeState, self.conversation_id)
                if row:
                    return dict(row.state_data or {})
        except Exception as e:
            logger.warning("Failed to load DB state for %s: %s", self.conversation_id, e)

        # One-time compatibility path for states created before DB migration.
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state for {self.conversation_id}: {e}")
        return {}

    def _save(self):
        try:
            from app.models import SessionLocal
            from app.models.agent_runtime_state import AgentRuntimeState
            with SessionLocal() as db:
                row = db.get(AgentRuntimeState, self.conversation_id)
                if row is None:
                    row = AgentRuntimeState(conversation_id=self.conversation_id, state_data={})
                    db.add(row)
                row.status = self._state.get("status")
                row.state_data = self._state
                db.commit()
        except Exception as e:
            logger.error(f"Failed to save state for {self.conversation_id}: {e}")

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    def set(self, key: str, value: Any):
        self._state[key] = value
        self._save()

    def clear(self):
        self._state = {}
        try:
            from app.models import SessionLocal
            from app.models.agent_runtime_state import AgentRuntimeState
            with SessionLocal() as db:
                db.query(AgentRuntimeState).filter(
                    AgentRuntimeState.conversation_id == self.conversation_id
                ).delete(synchronize_session=False)
                db.commit()
        except Exception as e:
            logger.error("Failed to clear DB state for %s: %s", self.conversation_id, e)
        if self.state_file.exists():
            self.state_file.unlink()

    def is_interrupted(self) -> bool:
        return self._state.get("status") == "interrupted"

    def set_interrupted(self, messages: List[dict], tool_history: List[dict], step: int, reflections: List[str]):
        self._state = {
            "status": "interrupted",
            "messages": messages,
            "tool_history": tool_history,
            "step": step,
            "reflections": reflections,
            "interrupted_at": datetime.now().isoformat(),
        }
        self._save()

    def get_resume_state(self) -> Optional[Dict[str, Any]]:
        if self.is_interrupted():
            return {
                "messages": self._state.get("messages", []),
                "tool_history": self._state.get("tool_history", []),
                "step": self._state.get("step", 0),
                "reflections": self._state.get("reflections", []),
            }
        return None

    def set_resumed(self):
        self._state["status"] = "resumed"
        self._save()

    def set_human_waiting(self, payload: Dict[str, Any]):
        self._state = {
            "status": "waiting_for_human",
            "human_review": payload,
            "waiting_at": datetime.now().isoformat(),
        }
        self._save()

    def is_waiting_for_human(self) -> bool:
        return self._state.get("status") == "waiting_for_human"

    def get_human_waiting(self) -> Optional[Dict[str, Any]]:
        if not self.is_waiting_for_human():
            return None
        value = self._state.get("human_review")
        return dict(value) if isinstance(value, dict) else None

    def finish_human_review(self, approved: bool, feedback: str = ""):
        self._state["status"] = "human_approved" if approved else "human_rejected"
        self._state["human_decision"] = {
            "approved": approved,
            "feedback": feedback,
            "decided_at": datetime.now().isoformat(),
        }
        self._save()


# Module-level cache
_state_cache: Dict[str, SessionState] = {}


def get_session_state(conversation_id: str) -> SessionState:
    if conversation_id not in _state_cache:
        _state_cache[conversation_id] = SessionState(conversation_id)
    else:
        # Multiple Uvicorn workers have separate caches but share this file.
        _state_cache[conversation_id]._state = _state_cache[conversation_id]._load()
    return _state_cache[conversation_id]
