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
import builtins
import sys
import os
import shutil

# 1. Block dangerous imports
for mod in %(deny)s:
    sys.modules[mod] = None

# 2. Restrict File I/O
_orig_open = builtins.open

def _safe_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
    if isinstance(file, int):
        return _orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)
    
    # Resolve path
    try:
        path = os.path.abspath(str(file))
        cwd = os.getcwd()
        
        # Check confinement
        if not path.startswith(cwd):
            raise PermissionError(f"Sandbox violation: Access to {file} outside working directory is denied.")
            
    except Exception as e:
        raise PermissionError(f"Sandbox violation: Invalid path {file}") from e

    return _orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

builtins.open = _safe_open

# 3. Disable File Deletion
def _deny(*args, **kwargs):
    raise PermissionError("Sandbox violation: This operation is disabled.")

os.remove = _deny
os.unlink = _deny
os.rmdir = _deny
shutil.rmtree = _deny

# 4. Disable other dangerous os functions
os.system = _deny
os.popen = _deny
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
    
    # Use local work dir if it exists, otherwise system temp
    work_dir = Path("work").resolve()
    if not work_dir.exists():
        work_dir = None
        
    with tempfile.TemporaryDirectory(dir=work_dir) as td:
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
