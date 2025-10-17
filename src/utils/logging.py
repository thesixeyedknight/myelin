from __future__ import annotations
import json, time, sys
from pathlib import Path
from typing import Any, Dict

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

def _now_ms():
    return int(time.time() * 1000)

class JsonConsoleLogger:
    def __init__(self, path: str | Path, level: str = "INFO", to_console: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self.level_name = level.upper()
        self.level = _LEVELS.get(self.level_name, 20)
        self.to_console = to_console

    def set_level(self, level: str):
        self.level_name = level.upper()
        self.level = _LEVELS.get(self.level_name, 20)

    def _emit_console(self, payload: Dict[str, Any]):
        lvl = payload.get("level", "INFO")
        if _LEVELS.get(lvl, 20) < self.level:
            return
        ts = payload.get("ts_ms", _now_ms())
        event = payload.get("event", "")
        # a short, readable one-liner to console
        msg = payload.get("msg") or payload.get("text") or ""
        print(f"[{lvl:<5} {ts}] {event} {('- ' + str(msg)) if msg else ''}")
        # if details present but not msg, print keys
        if not msg:
            keys = {k: v for k, v in payload.items() if k not in {"level", "ts_ms", "event"}}
            if keys:
                print("         ", json.dumps(keys)[:800])

    def log(self, level: str = "INFO", **kv):
        kv.setdefault("ts_ms", _now_ms())
        kv.setdefault("level", level.upper())
        # write JSON line
        self._fh.write(json.dumps(kv, ensure_ascii=False) + "\n")
        self._fh.flush()
        # mirror to console
        if self.to_console:
            self._emit_console(kv)

    # convenience
    def debug(self, **kv): self.log("DEBUG", **kv)
    def info(self, **kv):  self.log("INFO", **kv)
    def warn(self, **kv):  self.log("WARN", **kv)
    def error(self, **kv): self.log("ERROR", **kv)

    def close(self):
        self._fh.close()

# global
LOGGER = JsonConsoleLogger("logs/run.jsonl", level="INFO", to_console=True)
