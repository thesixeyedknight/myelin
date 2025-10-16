from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Callable, Any, Optional

CACHE_DIR = Path("work/.cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key(namespace: str, payload: Any) -> Path:
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return CACHE_DIR / f"{namespace}-{h}.json"


def disk_cache(namespace: str, ttl_none: Optional[int] = None):
    """Simple write-through cache decorator (no TTL pruning)."""
    def deco(fn: Callable[..., Any]):
        def wrapper(*args, **kwargs):
            path = _key(namespace, {"args": args, "kwargs": kwargs})
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            out = fn(*args, **kwargs)
            try:
                path.write_text(json.dumps(out), encoding="utf-8")
            except Exception:
                pass
            return out
        return wrapper
    return deco
