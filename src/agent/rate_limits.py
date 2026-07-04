from __future__ import annotations
import time
import json
from pathlib import Path
from datetime import datetime, date
from typing import Literal
from src.configs.settings import SETTINGS


# Legacy TokenBucket for backward compatibility (not used with new system)
class TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate_per_sec = refill_rate_per_sec
        self.tokens = capacity
        self.last = time.time()

    def take(self, n: int = 1):
        now = time.time()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self.last = now
        if self.tokens < n:
            needed = n - self.tokens
            time.sleep(max(0, needed / self.refill_rate_per_sec))
            self.tokens = 0
            self.last = time.time()
        else:
            self.tokens -= n


# Legacy LLM_RPM (not used with new cascading fallback)
LLM_RPM = TokenBucket(capacity=1, refill_rate_per_sec=2 / 60.0)


ModelTier = Literal["pro", "flash", "lite"]


class ModelManager:
    """Tracks daily usage and enforces quotas for tiered models."""
    
    def __init__(self, usage_file: str = "work/usage.json"):
        self.usage_file = Path(usage_file)
        self.usage_file.parent.mkdir(exist_ok=True)
        self.provider = SETTINGS.llm_provider
        self.quotas = {
            "pro": SETTINGS.quota_pro,
            "flash": SETTINGS.quota_flash,
            "lite": SETTINGS.quota_lite
        }
        if self.provider == "ollama":
            self.models = {
                "pro": SETTINGS.ollama_model_pro,
                "flash": SETTINGS.ollama_model_flash,
                "lite": SETTINGS.ollama_model_lite
            }
        else:
            self.models = {
                "pro": SETTINGS.model_pro,
                "flash": SETTINGS.model_flash,
                "lite": SETTINGS.model_lite
            }
        self.usage = self._load_usage()
    
    def _load_usage(self) -> dict:
        """Load usage stats from disk."""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, "r") as f:
                    data = json.load(f)
                    # Reset if it's a new day
                    if data.get("date") != str(date.today()):
                        return self._reset_usage()
                    return data
            except Exception:
                return self._reset_usage()
        return self._reset_usage()
    
    def _reset_usage(self) -> dict:
        """Reset usage for a new day."""
        return {
            "date": str(date.today()),
            "pro": 0,
            "flash": 0,
            "lite": 0
        }
    
    def _save_usage(self):
        """Persist usage stats to disk."""
        with open(self.usage_file, "w") as f:
            json.dump(self.usage, f, indent=2)
    
    def get_available_model(self, preferred_tier: ModelTier = "flash") -> tuple[str, ModelTier]:
        """
        Returns (model_name, tier) based on availability.
        Cascades from preferred -> lower tiers if quota exhausted.
        """
        # Ollama has no call limits, so there's nothing to ration - just use
        # whichever local model the user configured for this tier.
        if self.provider == "ollama":
            return self.models[preferred_tier], preferred_tier

        # Check if it's a new day
        if self.usage.get("date") != str(date.today()):
            self.usage = self._reset_usage()
            self._save_usage()
        
        # Try preferred tier first
        if self.usage[preferred_tier] < self.quotas[preferred_tier]:
            return self.models[preferred_tier], preferred_tier
        
        # Cascade to lower tiers
        tiers = ["lite", "flash", "pro"]
        if preferred_tier in tiers:
            # Try tiers in order of abundance
            for tier in tiers:
                if self.usage[tier] < self.quotas[tier]:
                    return self.models[tier], tier
        
        # All exhausted
        raise RuntimeError(
            f"All model quotas exhausted for today. "
            f"Pro: {self.usage['pro']}/{self.quotas['pro']}, "
            f"Flash: {self.usage['flash']}/{self.quotas['flash']}, "
            f"Lite: {self.usage['lite']}/{self.quotas['lite']}"
        )
    
    def increment(self, tier: ModelTier):
        """Record a successful request."""
        self.usage[tier] += 1
        self._save_usage()
    
    def get_stats(self) -> dict:
        """Return current usage stats."""
        if self.provider == "ollama":
            return {
                "date": self.usage["date"],
                "pro": f"{self.usage['pro']} (unlimited)",
                "flash": f"{self.usage['flash']} (unlimited)",
                "lite": f"{self.usage['lite']} (unlimited)",
            }
        return {
            "date": self.usage["date"],
            "pro": f"{self.usage['pro']}/{self.quotas['pro']}",
            "flash": f"{self.usage['flash']}/{self.quotas['flash']}",
            "lite": f"{self.usage['lite']}/{self.quotas['lite']}"
        }


# Global instance
MODEL_MANAGER = ModelManager()
