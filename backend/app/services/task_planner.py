# -*- coding: utf-8 -*-
"""Task Planner Service."""
import json
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = (
    "You are a task planner. Given a user request, generate a structured execution plan.\n\n"
    "Output format (JSON only, no markdown):\n"
    '{"plan": [{"step": 1, "action": "description", "tool": "optional_tool_name", "expected_result": "what success looks like"}]}\n\n'
    "Rules:\n"
    "1. Generate 1-5 steps. If task is trivial (single-step), output 1 step.\n"
    "2. Each step must be actionable and verifiable.\n"
    "3. Specify which tool to use if known (code_exec, file_read, file_write, web_search, url_fetch).\n"
    "4. Output ONLY the JSON object, no preamble or explanation."
)


class TaskPlanner:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    async def generate_plan(self, user_request, model=None, available_tools=None):
        if not self.llm_service:
            return self._fallback_plan(user_request)
        tools_hint = ", ".join(available_tools) if available_tools else "code_exec, file_read, file_write, web_search, url_fetch"
        prompt_messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": "Available tools: " + tools_hint + "\n\nRequest: " + user_request}
        ]
        try:
            chunks = []
            async for chunk in self.llm_service.call_model(prompt_messages, model=model, stream=False):
                chunks.append(chunk)
            raw = "".join(chunks).strip()
            plan = self._parse_plan(raw)
            if plan:
                return plan
        except Exception as e:
            logger.warning("Plan generation failed: " + str(e))
        return self._fallback_plan(user_request)

    def _parse_plan(self, raw):
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "plan" in data:
                return data["plan"]
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        backtick = chr(96)
        pattern = backtick * 3 + r"(?:json)?\s*(\{.*?\})\s*" + backtick * 3
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if isinstance(data, dict) and "plan" in data:
                    return data["plan"]
            except json.JSONDecodeError:
                pass

        m = re.search(r"\{[^{}]*\"plan\"[^{}]*\[.*?\][^{}]*\}", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "plan" in data:
                    return data["plan"]
            except json.JSONDecodeError:
                pass
        return []

    def _fallback_plan(self, user_request):
        return [{
            "step": 1,
            "action": "Respond to: " + (user_request[:100] if user_request else "user request"),
            "tool": None,
            "expected_result": "Direct answer"
        }]


_planner_instance = None


def get_planner(llm_service=None):
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = TaskPlanner(llm_service=llm_service)
    elif llm_service is not None:
        _planner_instance.llm_service = llm_service
    return _planner_instance