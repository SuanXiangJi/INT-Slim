# -*- coding: utf-8 -*-
"""
Agent base classes for multi-agent graph system.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GraphState:
    """Unified state that flows through the agent graph.
    
    Each agent reads from and writes to this state.
    """
    # ── Conversation context ──
    user_input: str = ""
    user_id: str = ""
    conversation_id: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    sandbox_path: str = ""

    # ── Diagnosis Agent outputs ──
    learner_profile: Optional[Dict[str, Any]] = None
    learner_mastery: Dict[str, Any] = field(default_factory=dict)
    cognitive_load: float = 0.0
    mastery_summary: str = ""

    # ── Task Agent outputs ──
    goal: str = ""
    skill_sequence: List[Dict[str, Any]] = field(default_factory=list)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)

    # ── Retrieval Agent outputs ──
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    graph_relations: List[Dict[str, Any]] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_summary: str = ""

    # ── Generation Agent outputs ──
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    # ── Review Agent outputs ──
    defects: List[Dict[str, Any]] = field(default_factory=list)
    review_summary: str = ""

    # ── Judge Agent outputs ──
    final_content: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    judge_reasoning: str = ""

    # ── Execution metadata ──
    executed_agents: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        for fld in self.__dataclass_fields__:
            d[fld] = getattr(self, fld)
        return d


class BaseAgent(ABC):
    """Abstract base for all agents in the multi-agent graph."""

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier for this agent."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this agent does."""
        ...

    @property
    def dependencies(self) -> List[str]:
        """Agent IDs that must execute before this one."""
        return []

    @abstractmethod
    async def process(self, state: GraphState) -> GraphState:
        """Execute this agent's logic, updating and returning state."""
        ...