# -*- coding: utf-8 -*-
"""LangGraph agent run/debug endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.schemas.user import User as UserSchema
from app.services.langgraph_multi_agent import (
    AgentId,
    list_langgraph_agents,
    make_initial_state,
    run_single_agent,
)
from app.utils.uuid import uuid_string_to_bytes


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class AgentRunRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000)
    conversation_id: Optional[str] = None
    answer: Optional[str] = None
    profile_context: str = ""
    direct_answer_mode: bool = False
    human_approved: bool = False
    top_k: int = Field(5, ge=1, le=10)


def _safe_state(state: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(state)
    output.pop("user_id_bytes", None)
    retrieval = output.get("retrieval") or []
    output["retrieval"] = [
        {
            "doc_id": item.get("doc_id"),
            "chunk_id": item.get("chunk_id"),
            "score": item.get("score"),
            "metadata": item.get("metadata") or {},
            "content": (item.get("content") or "")[:600],
        }
        for item in retrieval
    ]
    context = output.get("context")
    if isinstance(context, str) and len(context) > 12000:
        output["context"] = context[:12000] + "\n...[truncated]"
    return output


@router.get("/agents")
def list_agents(current_user: UserSchema = Depends(get_current_user)):
    return {"agents": list_langgraph_agents()}


@router.post("/{agent_id}")
def run_agent(
    agent_id: AgentId,
    req: AgentRunRequest,
    current_user: UserSchema = Depends(get_current_user),
):
    try:
        user_id = uuid_string_to_bytes(current_user.id)
        state = make_initial_state(
            user_id=user_id,
            conversation_id=req.conversation_id or "debug",
            user_input=req.content,
            profile_context=req.profile_context,
            direct_answer_mode=req.direct_answer_mode,
            answer=req.answer or "",
            human_approved=req.human_approved,
            top_k=req.top_k,
        )
        result = run_single_agent(agent_id, state)
        return {
            "agent_id": agent_id,
            "trace_id": result.get("trace_id"),
            "state": _safe_state(result),
            "events": result.get("events") or [],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
