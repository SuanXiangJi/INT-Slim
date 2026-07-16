# -* coding: utf-8 -*-
"""Tool Retry Service."""
import asyncio
import logging
from typing import Callable, Dict, Any, Optional, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_retries: int = 2
    initial_delay: float = 0.5
    backoff_factor: float = 2.0
    retry_on_errors: tuple = ("timeout", "timed out", "connection", "rate", "temporarily", "quota", "balance", "unavailable", "model not available", "context length", "internal server error", "503", "502", "504", "try again")

DEFAULT_RETRY = RetryConfig()


NO_RETRY_ERRORS = (
    "permission denied", "access denied", "not found",
    "invalid argument", "validation", "path traversal",
    "absolute path", "unsupported language",
)


def should_retry(error_msg):
    error_lower = (error_msg or '').lower()
    if any(feat in error_lower for feat in NO_RETRY_ERRORS):
        return False
    return any(feat in error_lower for feat in DEFAULT_RETRY.retry_on_errors)


async def execute_with_retry(tool_func, *args, config=None, on_retry=None, **kwargs):
    cfg = config or DEFAULT_RETRY
    last_error = None

    for attempt in range(cfg.max_retries + 1):
        try:
            result = await tool_func(*args, **kwargs)
            if attempt > 0:
                logger.info('Tool succeeded on attempt ' + str(attempt + 1))
            return result
        except Exception as e:
            last_error = e
            error_msg = str(e)

            if not should_retry(error_msg):
                logger.debug('Non-retryable error: ' + error_msg[:100])
                raise

            if attempt >= cfg.max_retries:
                logger.warning('Max retries exceeded: ' + error_msg[:100])
                raise

            delay = cfg.initial_delay * (cfg.backoff_factor ** attempt)
            logger.info('Retry ' + str(attempt + 1) + '/' + str(cfg.max_retries))

            if on_retry:
                try:
                    on_retry(attempt + 1, e)
                except Exception:
                    pass

            await asyncio.sleep(delay)

    raise last_error
