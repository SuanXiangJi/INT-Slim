# -*- coding: utf-8 -*-
"""Model Router Service - backend automatic model fallback"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    name: str
    provider: str
    priority: int = 0
    max_tokens: int = 8192


DEFAULT_MODEL_CHAIN = [
    ModelConfig(name="deepseek-v4-flash", provider="deepseek", priority=0),
    ModelConfig(name="deepseek-chat", provider="deepseek", priority=1),
    ModelConfig(name="minimax", provider="minimax", priority=2),
    ModelConfig(name="MiniMax-M2.7", provider="minimax", priority=3),
]

FALLBACK_ERRORS = (
    "rate limit", "quota", "insufficient balance",
    "model not available", "timeout", "service unavailable",
    "internal server error", "context length exceeded",
)


class ModelRouter:
    def __init__(self, llm_service=None, model_chain=None):
        self.llm_service = llm_service
        self.model_chain = model_chain or DEFAULT_MODEL_CHAIN
        self._chain_cache = {}

    def get_chain_for_model(self, primary_model):
        if primary_model in self._chain_cache:
            return self._chain_cache[primary_model]
        primary_name = primary_model.split(":")[-1] if ":" in primary_model else primary_model
        chain = []
        primary_found = False
        for model in self.model_chain:
            if primary_found or primary_name in model.name or model.name in primary_name:
                primary_found = True
                chain.append(model)
        if not primary_found:
            chain.insert(0, ModelConfig(name=primary_name, provider=primary_model.split(":")[0] if ":" in primary_model else "unknown", priority=-1))
        for model in self.model_chain:
            if model not in chain:
                chain.append(model)
        self._chain_cache[primary_model] = chain
        return chain

    def should_fallback(self, error):
        error_lower = (error or "").lower()
        return any(feat in error_lower for feat in FALLBACK_ERRORS)

    async def call_with_fallback(self, messages, primary_model, stream=False, **kwargs):
        if not self.llm_service:
            raise RuntimeError("LLM service not configured")
        chain = self.get_chain_for_model(primary_model)
        last_error = None
        for i, model in enumerate(chain):
            full_model = primary_model if i == 0 else (model.provider + ":" + model.name)
            try:
                logger.info("ModelRouter: trying " + full_model)
                if stream:
                    gen = self.llm_service.call_model(messages, model=full_model, stream=True, **kwargs)
                    return self._wrap_stream(gen, full_model), full_model
                else:
                    result = await self._call_non_stream(messages, full_model, **kwargs)
                    return result, full_model
            except Exception as e:
                error_msg = str(e)
                last_error = e
                logger.warning("ModelRouter: " + full_model + " failed: " + error_msg[:200])
                if not self.should_fallback(error_msg) and i == 0:
                    raise
                if i < len(chain) - 1:
                    logger.info("ModelRouter: falling back to " + chain[i+1].name)
                    continue
        raise RuntimeError("All models in chain failed. Last error: " + str(last_error))

    async def _call_non_stream(self, messages, model, **kwargs):
        # LLM service may be sync or async; handle both
        result = self.llm_service.call_model(messages, model=model, stream=False, **kwargs)
        # If result is async, await it
        if asyncio.iscoroutine(result):
            result = await result
        # If result is an async iterator / generator
        if hasattr(result, "__aiter__"):
            chunks = []
            async for chunk in result:
                chunks.append(chunk)
            return "".join(chunks)
        # If result is a sync iterator
        if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
            return "".join(str(c) for c in result)
        # Plain value (str)
        return str(result) if result is not None else ""

    async def _wrap_stream(self, gen, model_name):
        async for chunk in gen:
            yield chunk


_router_instance = None


def get_router(llm_service=None):
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter(llm_service=llm_service)
    elif llm_service is not None:
        _router_instance.llm_service = llm_service
    return _router_instance
