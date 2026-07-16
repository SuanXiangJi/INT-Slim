# -*- coding: utf-8 -*-
"""
Context Compressor Service
==========================

Compresses conversation history to fit within LLM context windows.
Strategies:
  1. Sliding window: keep recent N messages
  2. Token budget: trim oldest until within budget
  3. Summary: use LLM to summarize old messages into compact form
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# Model context windows (input tokens)
MODEL_CONTEXT_WINDOWS = {
    "deepseek-chat": 32000,
    "deepseek-v4-pro": 32000,
    "deepseek-v4-flash": 32000,
    "minimax": 32768,
    "MiniMax-M2.7": 32768,
    "MiniMax-M3": 65536,
}


class ContextCompressor:
    """Compress conversation history for LLM context windows."""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def get_context_window(self, model: str) -> int:
        """Get max context window for a model.
        Uses longest-match-first to avoid prefix collisions (e.g., 'minimax' shouldn't match 'MiniMax-M3')."""
        model_lower = (model or "").lower()
        # Sort keys by length descending so longer/specific names match first
        sorted_keys = sorted(MODEL_CONTEXT_WINDOWS.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key.lower() in model_lower:
                return MODEL_CONTEXT_WINDOWS[key]
        # Safe default for unknown models
        return 8000

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimate (English ~4 chars/token, Chinese ~1.5 chars/token)."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            # Count Chinese chars
            chinese_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
            english_chars = len(content) - chinese_chars
            total += chinese_chars + english_chars // 4
        return int(total)

    def compress(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        max_output_tokens: int = 2048,
        reserved_for_system: int = 500,
    ) -> List[Dict[str, Any]]:
        """Compress messages to fit within model context window.

        Returns the (possibly compressed) list of messages.
        System message is preserved if present.
        """
        if not messages:
            return messages

        context_window = self.get_context_window(model)
        budget = context_window - max_output_tokens - reserved_for_system

        current_tokens = self.estimate_tokens(messages)

        if current_tokens <= budget:
            return messages  # Already fits

        # Split system vs conversation
        system_msgs = [m for m in messages if m.get("role") == "system"]
        conv_msgs = [m for m in messages if m.get("role") != "system"]

        # Keep all system messages, trim conversation
        system_tokens = self.estimate_tokens(system_msgs)
        conv_budget = budget - system_tokens

        # Sliding window: keep most recent messages
        kept = []
        running_tokens = 0

        # Always keep the last user message
        if conv_msgs and conv_msgs[-1].get("role") == "user":
            kept.insert(0, conv_msgs[-1])
            conv_msgs = conv_msgs[:-1]
            running_tokens = self.estimate_tokens(kept)

        # Add older messages from most recent backwards
        for msg in reversed(conv_msgs):
            msg_tokens = self.estimate_tokens([msg])
            if running_tokens + msg_tokens > conv_budget:
                break
            kept.insert(0, msg)
            running_tokens += msg_tokens

        # If we had to drop a lot, add a summary note
        dropped_count = len(conv_msgs) + (1 if messages and messages[-1].get("role") == "user" else 0) - len(kept)
        if dropped_count > 2:
            summary_msg = {
                "role": "system",
                "content": f"[Context note: {dropped_count} earlier messages were omitted to fit context window. Conversation focus is on the recent turns.]"
            }
            result = system_msgs + [summary_msg] + kept
        else:
            result = system_msgs + kept

        final_tokens = self.estimate_tokens(result)
        logger.info(f"Context compressed: {len(messages)} -> {len(result)} messages, ~{current_tokens} -> ~{final_tokens} tokens")

        return result

    async def summarize_old_messages(
        self,
        messages: List[Dict[str, Any]],
        model: str,
    ) -> str:
        """Use LLM to summarize old messages into compact form."""
        if not self.llm_service or not messages:
            return ""

        # Build summarization prompt
        text_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            # Truncate long content
            if len(content) > 500:
                content = content[:500] + "..."
            text_parts.append(f"[{role}] {content}")

        prompt_text = "\n".join(text_parts)

        summary_prompt = [
            {
                "role": "system",
                "content": "You are a conversation summarizer. Compress the following conversation history into a concise paragraph (under 200 words) preserving: 1) user goals, 2) key decisions, 3) tools used and their results, 4) current task state. Output ONLY the summary, no preamble."
            },
            {
                "role": "user",
                "content": f"Summarize this conversation:\n\n{prompt_text}"
            }
        ]

        try:
            response_chunks = []
            async for chunk in self.llm_service.call_model(summary_prompt, model=model, stream=False):
                response_chunks.append(chunk)

            response = "".join(response_chunks).strip()
            return response[:1500]  # Cap summary length
        except Exception as e:
            logger.warning(f"Failed to summarize messages: {e}")
            return ""


# Module-level singleton (lazy-initialized)
_compressor_instance: Optional[ContextCompressor] = None


def get_compressor(llm_service=None) -> ContextCompressor:
    """Get the compressor singleton."""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = ContextCompressor(llm_service=llm_service)
    elif llm_service is not None:
        _compressor_instance.llm_service = llm_service
    return _compressor_instance
