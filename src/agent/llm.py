from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from src.configs.settings import SETTINGS
from src.agent.rate_limits import LLM_RPM
from src.utils.logging import LOGGER
from pathlib import Path
import time

from google import genai
from google.genai import types, errors

class LLMClient:
    def __init__(self, model: Optional[str] = None, save_io: bool | None = None):
        self.model_name = model or SETTINGS.gemini_model
        self.client = genai.Client(api_key=SETTINGS.gemini_api_key or None)
        self.save_io = SETTINGS.save_llm_io if save_io is None else save_io
        # fetch model limits (best-effort)
        try:
            info = self.client.models.get(model=self.model_name)
            self.input_token_limit = getattr(info, "input_token_limit", None)
            self.output_token_limit = getattr(info, "output_token_limit", None)
            LOGGER.debug(event="llm_model_info", model=self.model_name,
                         input_token_limit=self.input_token_limit,
                         output_token_limit=self.output_token_limit)
        except Exception as e:
            LOGGER.warn(event="llm_model_info_failed", model=self.model_name, msg=str(e))
            self.input_token_limit = None
            self.output_token_limit = None

    def _dump_io(self, tag: str, kind: str, text: str):
        if not self.save_io:
            return
        d = Path("logs/llm")
        d.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        (d / f"{ts}_{tag}_{kind}.txt").write_text(text, encoding="utf-8")

    def count_tokens(self, system_prompt: str, user_prompt: str) -> int:
        combined = (system_prompt or "") + "\n" + (user_prompt or "")
        try:
            resp = self.client.models.count_tokens(model=self.model_name, contents=combined)
            return int(getattr(resp, "total_tokens", 0))
        except Exception:
            return 0

    @retry(wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(3))
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        response_mime_type: str | None = None,
        tag: str = "generic",
    ) -> Tuple[str, Dict[str, Any]]:
        LLM_RPM.take(1)
        # preflight token count (best-effort)
        pre_tokens = self.count_tokens(system_prompt, user_prompt)
        LOGGER.info(event="llm_generate_start", model=self.model_name,
                    tag=tag, response_mime_type=response_mime_type,
                    pre_tokens=pre_tokens)

        self._dump_io(tag, "prompt_system", system_prompt)
        self._dump_io(tag, "prompt_user", user_prompt)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type=response_mime_type,  # e.g., "application/json"
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=config,
            )
        except errors.APIError as e:
            LOGGER.error(event="llm_generate_error", tag=tag, msg=str(e))
            raise

        text = response.text or ""
        self._dump_io(tag, "response_text", text)
        usage = getattr(response, "usage_metadata", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "prompt_token_count": getattr(usage, "prompt_token_count", None),
                "candidates_token_count": getattr(usage, "candidates_token_count", None),
                "total_token_count": getattr(usage, "total_token_count", None),
            }
        LOGGER.info(event="llm_generate_ok", tag=tag, usage=usage_dict)
        return text, usage_dict
