from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from src.configs.settings import SETTINGS
from src.agent.rate_limits import MODEL_MANAGER, ModelTier

# Google GenAI SDK (GA)
from google import genai
from google.genai import types, errors


class LLMClient:
    def __init__(self, model: Optional[str] = None):
        # Note: model param is for backward compatibility; tier is now preferred
        self.model_name = model or SETTINGS.gemini_model
        # Client picks API key from env automatically; we also pass explicitly if present.
        self.client = genai.Client(api_key=SETTINGS.gemini_api_key or None)

        # Get model token limits (best-effort)
        try:
            info = self.client.models.get(model=self.model_name)
            self.input_token_limit = getattr(info, "input_token_limit", None)
            self.output_token_limit = getattr(info, "output_token_limit", None)
        except Exception:
            self.input_token_limit = None
            self.output_token_limit = None

    def count_tokens(self, system_prompt: str, user_prompt: str) -> int:
        """Model-specific token count using SDK; returns 0 if it fails."""
        combined = (system_prompt or "") + "\n" + (user_prompt or "")
        try:
            resp = self.client.models.count_tokens(model=self.model_name, contents=combined)
            return int(getattr(resp, "total_tokens", 0))
        except Exception:
            return 0

    @retry(wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(5))
    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        tier: ModelTier = "flash"
    ) -> Tuple[str, Dict[str, Any], ModelTier]:
        """
        Generate text with cascading fallback.
        Returns: (text, usage_metadata_dict, actual_tier_used).
        """
        # Get model based on tier and quota
        model_name, actual_tier = MODEL_MANAGER.get_available_model(tier)
        
        config = types.GenerateContentConfig(system_instruction=system_prompt)
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=config,
            )
            # Record successful request
            MODEL_MANAGER.increment(actual_tier)
            
            # Log to audit trail
            from src.agent.usage_auditor import USAGE_AUDITOR
            
        except errors.APIError as e:
            # Check if it's a 429 (quota exceeded)
            if "429" in str(e) or "Resource exhausted" in str(e):
                # Let ModelManager handle fallback on next call
                raise
            # Let tenacity handle other retries
            raise

        text = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "prompt_token_count": getattr(usage, "prompt_token_count", None),
                "candidates_token_count": getattr(usage, "candidates_token_count", None),
                "total_token_count": getattr(usage, "total_token_count", None),
                "tier_used": actual_tier,
                "quota_stats": MODEL_MANAGER.get_stats()
            }
            
            # Audit log the request
            USAGE_AUDITOR.log_request(
                tier=actual_tier,
                model=model_name,
                usage_metadata=usage_dict,
                operation="generate"
            )
            
        return text, usage_dict, actual_tier

    def embed(self, text: str) -> list[float]:
        """Generate embeddings for a single string."""
        try:
            resp = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            return resp.embeddings[0].values
        except Exception:
            return []
