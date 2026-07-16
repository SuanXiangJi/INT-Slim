import os
import json
import asyncio
from typing import Generator, Dict, Any, AsyncGenerator, List, Optional, Union
from openai import AsyncOpenAI, OpenAI
from app.config import settings
from app.services.prompt_service import prompt_service

LLM_REQUEST_TIMEOUT = 90
LLM_STREAM_CHUNK_TIMEOUT = 45


class LLMService:
    """LLM Service for calling LLM models using OpenAI compatible API"""

    # Provider configurations
    PROVIDERS = {
        "deepseek": {
            "api_key": None,  # Set dynamically
            "base_url": "https://api.deepseek.com/v1",
            "models": ["deepseek-chat", "deepseek-v4-pro", "deepseek-v4-flash"]
        },
        "minimax": {
            "api_key": None,
            "base_url": "https://api.minimax.chat/v1",
            "models": ["MiniMax-M3", "MiniMax-M2.7"]
        },
    }

    def __init__(self, provider: str = "deepseek", model: str = None):
        self.provider = provider
        self._client = None
        self._async_client = None
        self._api_key = None
        self._base_url = None

        # Initialize based on provider
        self._init_provider(provider)

        # Get model from config or use provided
        if model:
            self.model = model
        else:
            default_config = prompt_service.get_default_model()
            self.model = default_config.get("name", "deepseek-chat")

        self.default_model_config = prompt_service.get_default_model()

    def _init_provider(self, provider: str):
        """Initialize provider settings"""
        if provider == "deepseek":
            self._api_key = settings.deepseek_api_key
            self._base_url = "https://api.deepseek.com/v1"
        elif provider == "minimax":
            self._api_key = settings.minimax_api_key
            self._base_url = "https://api.minimax.chat/v1"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @property
    def client(self):
        """Lazy initialization of OpenAI client"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=LLM_REQUEST_TIMEOUT,
            )
        return self._client

    @property
    def async_client(self):
        """Async client used by the SSE/agent path so it never blocks a worker loop."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=LLM_REQUEST_TIMEOUT,
                max_retries=0,
            )
        return self._async_client

    def get_available_providers(self) -> list:
        """Get list of available providers with their models"""
        providers = []
        for name, config in self.PROVIDERS.items():
            # Check if API key is configured
            api_key = getattr(settings, f"{name}_api_key", None)
            if api_key:
                providers.append({
                    "name": name,
                    "models": config["models"],
                    "has_api_key": bool(api_key)
                })
        return providers

    def _parse_model(self, model: str) -> tuple[str, str, str]:
        """Parse model string and return (resolved_model_name, provider_prefix, actual_model).

        Handles formats:
        - "provider:model" (e.g. "deepseek:deepseek-chat") -> (model_name, provider, actual_model)
        - "provider-model" (e.g. "minimax-m3.0") -> (fixed_model_name, provider, actual_model)
        - plain model name -> (model_name, current_provider, None)
        """
        if model and ":" in model:
            # Format: "provider:model"
            provider_prefix, actual_model = model.split(":", 1)
            resolved = self._resolve_model_name(provider_prefix, actual_model)
            return (resolved, provider_prefix, actual_model)
        elif model and "-" in model:
            # Only treat the first segment as a provider slug for MiniMax.
            # DeepSeek's official model names already start with "deepseek-"
            # (e.g. "deepseek-v4-pro"), so splitting on "-" would break them.
            known_providers = ["minimax"]
            parts = model.split("-", 1)
            if parts[0].lower() in known_providers:
                provider_prefix, actual_model = parts
                resolved = self._resolve_model_name(provider_prefix, actual_model)
                return (resolved, provider_prefix, actual_model)
        return (model, self.provider, None)

    def _resolve_model_name(self, provider: str, model: str) -> str:
        """Resolve model name for a specific provider, fixing naming conventions."""
        if provider == "minimax":
            lower = model.lower()
            if lower.startswith("minimax-"):
                return model
            elif lower.startswith("m"):
                # m2.7 -> MiniMax-M2.7, m3 -> MiniMax-M3, m3.0 -> MiniMax-M3
                resolved = "MiniMax-" + model.replace("m", "M", 1)
                if resolved.endswith(".0"):
                    resolved = resolved[:-2]
                return resolved
        if provider == "deepseek":
            # Safegaurd: map generic "deepseek" or old names to latest stable model
            lower = model.lower().strip()
            if lower in ("deepseek", "deepseek-chat", ""):
                return "deepseek-v4-flash"
        return model

    def call_model(self, messages: list[dict], temperature: float = None, top_p: float = None, model: str = None, stream: bool = False):
        """Call LLM with specified or default model"""
        model = model or self.model
        resolved_model, provider_prefix, _ = self._parse_model(model)

        # Switch provider if different
        if provider_prefix != self.provider:
            self.provider = provider_prefix
            self._init_provider(provider_prefix)
            self._client = None
            self._async_client = None
            self._async_client = None

        temperature = temperature or self.default_model_config.get("temperature", 0.6)
        top_p = top_p or self.default_model_config.get("top_p", 0.8)
        max_tokens = self.default_model_config.get("max_tokens", 8192)

        if stream:
            return self._stream_call(resolved_model, messages, temperature, top_p, max_tokens)
        else:
            return self._non_stream_call(resolved_model, messages, temperature, top_p, max_tokens)

    def _non_stream_call(self, model: str, messages: list[dict], temperature: float, top_p: float, max_tokens: int) -> str:
        """Non-streaming LLM call"""
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False
        )
        return completion.choices[0].message.content

    def _stream_call(self, model: str, messages: list[dict], temperature: float, top_p: float, max_tokens: int) -> Generator[str, None, None]:
        """Streaming LLM call"""
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True
        )

        for chunk in completion:
            if chunk.choices:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content

    def format_message_history(self, messages: list[dict]) -> list[dict]:
        """Format message history for LLM input"""
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return formatted_messages

    def call_model_with_tools(
        self,
        messages: list[dict],
        tools: Optional[List[dict]] = None,
        temperature: float = None,
        top_p: float = None,
        model: str = None,
        stream: bool = True,
        max_tokens: int = None
    ) -> Union[Generator, AsyncGenerator, dict]:
        """
        Call LLM with tools/function calling support
        """
        model = model or self.model
        resolved_model, provider_prefix, _ = self._parse_model(model)

        # Switch provider if different
        if provider_prefix != self.provider:
            self.provider = provider_prefix
            self._init_provider(provider_prefix)
            self._client = None

        temperature = temperature or self.default_model_config.get("temperature", 0.6)
        top_p = top_p or self.default_model_config.get("top_p", 0.8)
        max_tokens = max_tokens or self.default_model_config.get("max_tokens", 8192)

        if stream:
            return self._stream_call_with_tools(resolved_model, messages, tools, temperature, top_p, max_tokens)
        else:
            return self._non_stream_call_with_tools(resolved_model, messages, tools, temperature, top_p, max_tokens)

    def _non_stream_call_with_tools(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[List[dict]],
        temperature: float,
        top_p: float,
        max_tokens: int
    ) -> dict:
        """Non-streaming LLM call with tools"""
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = self.client.chat.completions.create(**kwargs)

        message = completion.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None)
        if not reasoning_content:
            model_extra = getattr(message, "model_extra", None) or {}
            reasoning_content = model_extra.get("reasoning_content", "")
        result = {
            "content": message.content or "",
            "reasoning_content": reasoning_content or "",
        }

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]

        return result

    async def _stream_call_with_tools(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[List[dict]],
        temperature: float,
        top_p: float,
        max_tokens: int
    ) -> AsyncGenerator[dict, None]:
        """Streaming LLM call with tools support (async version)"""
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = await asyncio.wait_for(
            self.async_client.chat.completions.create(**kwargs),
            timeout=LLM_REQUEST_TIMEOUT,
        )

        stream = None
        try:
            stream = completion.__aiter__()
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        anext(stream),
                        timeout=LLM_STREAM_CHUNK_TIMEOUT,
                    )
                except StopAsyncIteration:
                    break
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                reasoning_content = getattr(choice.delta, "reasoning_content", None)
                if not reasoning_content:
                    model_extra = getattr(choice.delta, "model_extra", None) or {}
                    reasoning_content = model_extra.get("reasoning_content", "")
                if reasoning_content:
                    yield {"type": "reasoning", "content": reasoning_content}

                if choice.delta.content:
                    yield {"type": "content", "content": choice.delta.content}

                if choice.delta.tool_calls:
                    for tc_delta in choice.delta.tool_calls:
                        yield {
                            "type": "tool_call",
                            "index": getattr(tc_delta, "index", 0),
                            "tool_call_id": tc_delta.id,
                            "function": {
                                "name": tc_delta.function.name or "",
                                "arguments": tc_delta.function.arguments or ""
                            }
                        }

                if choice.finish_reason:
                    yield {"type": "done", "finish_reason": choice.finish_reason}
                    break
        finally:
            if stream is not None and hasattr(stream, "aclose"):
                try:
                    await stream.aclose()
                except Exception:
                    pass
            close = getattr(completion, "close", None) or getattr(completion, "aclose", None)
            if close:
                try:
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
                except Exception:
                    pass


# Create a singleton instance (default to deepseek)
llm_service = LLMService(provider="deepseek")

