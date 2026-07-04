from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
import time

from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from src.configs.settings import SETTINGS
from src.agent.rate_limits import MODEL_MANAGER, ModelTier, LLM_RPM
from src.utils.logging import LOGGER
from src.llm.providers import get_provider, QuotaExceededError


class LLMClient:
    def __init__(self, model: Optional[str] = None, save_io: bool | None = None):
        # Note: model param is for backward compatibility (used by
        # src/agent/token_budget.py to count tokens for a specific model);
        # tier is now preferred for generate().
        self.provider = get_provider(SETTINGS.llm_provider)
        default_model = (
            SETTINGS.ollama_model_flash if SETTINGS.llm_provider == "ollama" else SETTINGS.gemini_model
        )
        self.model_name = model or default_model
        self.save_io = SETTINGS.save_llm_io if save_io is None else save_io

    def _dump_io(self, tag: str, kind: str, text: str):
        if not self.save_io:
            return
        d = Path("logs/llm")
        d.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        (d / f"{ts}_{tag}_{kind}.txt").write_text(text, encoding="utf-8")

    def count_tokens(self, system_prompt: str, user_prompt: str) -> int:
        """Model-specific token count via the active provider; returns 0 if it fails."""
        try:
            return self.provider.count_tokens(system_prompt, user_prompt, self.model_name)
        except Exception:
            return 0

    @retry(wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(5))
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tier: ModelTier = "flash",
        *,
        response_mime_type: str | None = None,
        tag: str = "generic",
    ) -> Tuple[str, Dict[str, Any], ModelTier]:
        """
        Generate text with cascading fallback (tier -> lower tiers on daily quota
        exhaustion), basic RPM throttling, optional JSON-mode output, and optional
        full prompt/response dumps to logs/llm/ (enable via --save-llm / SAVE_LLM_IO).

        Returns: (text, usage_metadata_dict, actual_tier_used).
        """
        LLM_RPM.take(1)  # burst protection, independent of the daily quota tracking below

        # Get model based on tier and quota
        model_name, actual_tier = MODEL_MANAGER.get_available_model(tier)

        pre_tokens = self.count_tokens(system_prompt, user_prompt)
        LOGGER.info(
            event="llm_generate_start",
            model=model_name,
            tier=actual_tier,
            tag=tag,
            response_mime_type=response_mime_type,
            pre_tokens=pre_tokens,
        )
        self._dump_io(tag, "prompt_system", system_prompt)
        self._dump_io(tag, "prompt_user", user_prompt)

        try:
            text, raw_usage = self.provider.generate(system_prompt, user_prompt, model_name, response_mime_type)
            # Record successful request
            MODEL_MANAGER.increment(actual_tier)
        except QuotaExceededError as e:
            LOGGER.error(event="llm_generate_error", tag=tag, tier=actual_tier, msg=str(e))
            # Let ModelManager handle fallback on next call
            raise
        except Exception as e:
            LOGGER.error(event="llm_generate_error", tag=tag, tier=actual_tier, msg=str(e))
            # Let tenacity handle other retries
            raise

        self._dump_io(tag, "response_text", text)

        usage_dict: Dict[str, Any] = {}
        if raw_usage:
            usage_dict = {
                **raw_usage,
                "tier_used": actual_tier,
                "quota_stats": MODEL_MANAGER.get_stats(),
            }

            # Audit log the request
            from src.agent.usage_auditor import USAGE_AUDITOR

            USAGE_AUDITOR.log_request(
                tier=actual_tier,
                model=model_name,
                usage_metadata=usage_dict,
                operation="generate",
            )

        LOGGER.info(event="llm_generate_ok", tag=tag, tier=actual_tier, usage=usage_dict)
        return text, usage_dict, actual_tier

    def embed(self, text: str) -> list[float]:
        """Generate embeddings for a single string using the active provider."""
        embed_model = SETTINGS.ollama_embed_model if SETTINGS.llm_provider == "ollama" else "text-embedding-004"
        try:
            return self.provider.embed(text, embed_model)
        except Exception:
            return []
