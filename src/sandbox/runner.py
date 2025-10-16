from __future__ import annotations
import subprocess
import tempfile
import textwrap
import os
import resource
import sys
from pathlib import Path
from src.configs.settings import SETTINGS

DENY_IMPORTS = {"socket", "subprocess", "ssl", "urllib", "http", "ftplib"}

POLICY_PREAMBLE = """
import builtins, sys
for mod in %(deny)s:
    sys.modules[mod] = None
# Simple guard: prevent open network by sabotaging socket
sys.modules['socket'] = None
"""


def _limit_resources():
    # CPU seconds
    resource.setrlimit(resource.RLIMIT_CPU, (SETTINGS.max_worker_seconds, SETTINGS.max_worker_seconds))
    # Address space (bytes)
    mem = SETTINGS.max_worker_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))


def run_python(code: str) -> dict:
    policy = POLICY_PREAMBLE % {"deny": repr(tuple(DENY_IMPORTS))}
    wrapped = policy + "\n" + textwrap.dedent(code)
    with tempfile.TemporaryDirectory(dir="/app/work") as td:
        script = Path(td) / "snippet.py"
        script.write_text(wrapped, encoding="utf-8")
        env = os.environ.copy()
        env["NO_NETWORK"] = "1"
        try:
            p = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                env=env,
                timeout=SETTINGS.max_worker_seconds,
                preexec_fn=_limit_resources,
            )
            return {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "TIMEOUT"}
