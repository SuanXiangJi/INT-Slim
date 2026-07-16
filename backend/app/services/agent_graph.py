# -*- coding: utf-8 -*-
"""
Agent Graph Engine - orchestrate multiple agents in a directed acyclic graph.

Each agent reads from and writes to GraphState. The engine runs agents
in topological order, passing state between them.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Type, AsyncGenerator, Any
from app.agents.base import BaseAgent, GraphState

logger = logging.getLogger(__name__)


class AgentGraph:
    """Orchestrates multiple agents as a DAG."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._order: List[str] = []

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its agent_id."""
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent '{agent.agent_id}' already registered")
        self._agents[agent.agent_id] = agent

    def set_pipeline(self, agent_ids: List[str]) -> None:
        """Set linear execution order (simplest DAG for MVP)."""
        for aid in agent_ids:
            if aid not in self._agents:
                raise ValueError(f"Agent '{aid}' not registered")
        self._order = list(agent_ids)

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_id)

    @property
    def pipeline(self) -> List[str]:
        return list(self._order)

    @property
    def agent_ids(self) -> List[str]:
        return list(self._agents.keys())

    async def run(self, state: GraphState) -> GraphState:
        """Execute all agents in pipeline order. Returns final state."""
        for agent_id in self._order:
            agent = self._agents[agent_id]
            logger.info("[AgentGraph] Running: %s (%s)", agent_id, agent.name)
            try:
                state = await agent.process(state)
                state.executed_agents.append(agent_id)
                logger.info("[AgentGraph] Done: %s", agent_id)
            except Exception as exc:
                logger.exception("[AgentGraph] Error in %s: %s", agent_id, exc)
                state.errors.append({"agent": agent_id, "error": str(exc)})
        return state

    async def run_stream(self, state: GraphState) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute agents and yield streaming events for SSE."""
        for agent_id in self._order:
            agent = self._agents[agent_id]
            yield {"type": "agent_start", "data": {"agent_id": agent_id, "name": agent.name}}

            try:
                # Let the agent run; it yields events internally
                async for event in agent.process_stream(state):
                    yield event

                state.executed_agents.append(agent_id)
                yield {"type": "agent_done", "data": {"agent_id": agent_id, "name": agent.name}}

            except Exception as exc:
                logger.exception("[AgentGraph] Error in %s", agent_id)
                state.errors.append({"agent": agent_id, "error": str(exc)})
                yield {"type": "agent_error", "data": {"agent_id": agent_id, "error": str(exc)}}

        yield {"type": "graph_done", "data": {"executed_agents": state.executed_agents, "errors": state.errors}}

    def describe(self) -> Dict[str, Any]:
        """Return a description of the graph for debugging/API."""
        return {
            "agents": {
                aid: {
                    "name": a.name,
                    "description": a.description,
                    "dependencies": a.dependencies,
                }
                for aid, a in self._agents.items()
            },
            "pipeline": self._order,
        }


# ── Singleton ──
_agent_graph: Optional[AgentGraph] = None


def get_agent_graph() -> AgentGraph:
    """Get or create the global agent graph singleton."""
    global _agent_graph
    if _agent_graph is None:
        from app.agents.diagnosis_agent import DiagnosisAgent
        from app.agents.task_agent import TaskAgent
        from app.agents.retrieval_agent import RetrievalAgent
        from app.agents.generation_agent import GenerationAgent
        from app.agents.review_agent import ReviewAgent
        from app.agents.judge_agent import JudgeAgent

        _agent_graph = AgentGraph()
        _agent_graph.register(DiagnosisAgent())
        _agent_graph.register(TaskAgent())
        _agent_graph.register(RetrievalAgent())
        _agent_graph.register(GenerationAgent())
        _agent_graph.register(ReviewAgent())
        _agent_graph.register(JudgeAgent())
        _agent_graph.set_pipeline([
            "diagnosis",
            "task",
            "retrieval",
            "generation",
            "review",
            "judge",
        ])
    return _agent_graph