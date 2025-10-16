from __future__ import annotations
import json
import time
from pathlib import Path


class JsonLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def log(self, **kv):
        kv.setdefault("ts", time.time())
        self._fh.write(json.dumps(kv) + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


LOGGER = JsonLogger("logs/run.jsonl")
