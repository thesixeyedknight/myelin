from __future__ import annotations
from pathlib import Path
from src.tools.registry import tool

ALLOW_READ = [Path("data").resolve()]
ALLOW_WRITE = [Path("work").resolve()]


@tool("ReadFile")
def read_file(path: str) -> str:
    p = Path(path).resolve()
    if not any(str(p).startswith(str(a)) for a in ALLOW_READ):
        raise PermissionError("Read outside allowed dirs")
    return p.read_text(encoding="utf-8")


@tool("WriteFile")
def write_file(path: str, content: str) -> str:
    p = Path(path).resolve()
    if not any(str(p).startswith(str(a)) for a in ALLOW_WRITE):
        raise PermissionError("Write outside allowed dirs")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)
