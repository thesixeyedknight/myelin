"""Model-specific token counting via Google GenAI SDK.
Falls back to rough estimate if the SDK call fails.
"""
from __future__ import annotations
from src.agent.llm import LLMClient

_APPROX_DIVISOR = 4  # ~4 chars per token (fallback)


def estimate_tokens_fallback(*texts: str) -> int:
    return sum(len(t) for t in texts) // _APPROX_DIVISOR


def estimate_tokens(model_name: str, system_prompt: str, user_prompt: str) -> int:
    try:
        llm = LLMClient(model=model_name)
        n = llm.count_tokens(system_prompt, user_prompt)
        return n or estimate_tokens_fallback(system_prompt, user_prompt)
    except Exception:
        return estimate_tokens_fallback(system_prompt, user_prompt)
