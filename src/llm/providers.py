from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from src.configs.settings import SETTINGS


class QuotaExceededError(Exception):
    """Raised by a provider when it hits a rate/quota limit (e.g. Gemini 429)."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        response_mime_type: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Returns (text, usage_metadata_dict). usage_metadata_dict may be empty."""

    @abstractmethod
    def count_tokens(self, system_prompt: str, user_prompt: str, model_name: str) -> int:
        """Best-effort token count for the given model; may raise on failure."""

    @abstractmethod
    def embed(self, text: str, model_name: str) -> List[float]:
        """Embedding vector for text; may raise on failure."""


class GeminiProvider(LLMProvider):
    def __init__(self):
        from google import genai

        self.client = genai.Client(api_key=SETTINGS.gemini_api_key or None)

    def generate(self, system_prompt, user_prompt, model_name, response_mime_type=None):
        from google.genai import types, errors

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type=response_mime_type,
        )
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=config,
            )
        except errors.APIError as e:
            if "429" in str(e) or "Resource exhausted" in str(e):
                raise QuotaExceededError(str(e)) from e
            raise

        text = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        usage_dict: Dict[str, Any] = {}
        if usage:
            usage_dict = {
                "prompt_token_count": getattr(usage, "prompt_token_count", None),
                "candidates_token_count": getattr(usage, "candidates_token_count", None),
                "total_token_count": getattr(usage, "total_token_count", None),
            }
        return text, usage_dict

    def count_tokens(self, system_prompt, user_prompt, model_name):
        combined = (system_prompt or "") + "\n" + (user_prompt or "")
        resp = self.client.models.count_tokens(model=model_name, contents=combined)
        return int(getattr(resp, "total_tokens", 0))

    def embed(self, text, model_name):
        resp = self.client.models.embed_content(model=model_name, contents=text)
        return resp.embeddings[0].values


class OllamaProvider(LLMProvider):
    """Local Ollama backend. No quota/rate limiting applies - Ollama has no
    call limits, so ModelManager skips quota gating entirely for this provider
    (see src/agent/rate_limits.py)."""

    def __init__(self):
        import ollama

        self.client = ollama.Client(host=SETTINGS.ollama_host)

    def generate(self, system_prompt, user_prompt, model_name, response_mime_type=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        kwargs: Dict[str, Any] = {}
        if response_mime_type == "application/json":
            kwargs["format"] = "json"

        response = self.client.chat(model=model_name, messages=messages, **kwargs)
        text = response["message"]["content"]
        # Ollama doesn't report token usage the way Gemini does.
        return text, {}

    def count_tokens(self, system_prompt, user_prompt, model_name):
        # No cheap token-counting endpoint; callers fall back to a rough
        # chars-per-token estimate (see src/agent/token_budget.py).
        return 0

    def embed(self, text, model_name):
        resp = self.client.embeddings(model=model_name, prompt=text)
        return resp["embedding"]


_PROVIDERS: Dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    """Return a cached provider instance for the given name ('gemini' or 'ollama')."""
    if name not in _PROVIDERS:
        if name == "gemini":
            _PROVIDERS[name] = GeminiProvider()
        elif name == "ollama":
            _PROVIDERS[name] = OllamaProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {name!r}")
    return _PROVIDERS[name]
