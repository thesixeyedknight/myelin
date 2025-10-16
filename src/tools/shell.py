from __future__ import annotations
import subprocess
import shlex
import os
from src.tools.registry import tool

SAFE_BIN = {"wc", "head", "tail", "cut", "sort", "uniq", "awk"}


@tool("SafeShell")
def safe_shell(cmd: str) -> str:
    prog = shlex.split(cmd)[0]
    if prog not in SAFE_BIN:
        raise PermissionError("Command not allowed")
    env = os.environ.copy()
    env["NO_NETWORK"] = "1"
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, timeout=5)
    return out.stdout + ("\n" + out.stderr if out.stderr else "")
