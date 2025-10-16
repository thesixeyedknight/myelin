from src.sandbox.runner import run_python

def test_safe_code_runs():
    res = run_python("print(1+1)")
    assert res["returncode"] == 0
    assert res["stdout"].strip() == "2"
