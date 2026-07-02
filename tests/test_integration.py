import json
import pytest
from unittest.mock import MagicMock, patch
from src.agent.orchestrator import Orchestrator
from src.utils.schema import Plan, Evidence

@pytest.fixture
def mock_llm():
    with patch("src.agent.orchestrator.LLMClient") as MockLLM:
        client = MockLLM.return_value
        yield client

@pytest.fixture
def mock_tools():
    with patch("src.agent.orchestrator.T") as MockTools:
        yield MockTools

def test_orchestrator_run_flow(mock_llm, mock_tools):
    # Setup LLM responses
    # 1. Plan generation
    plan_json = json.dumps({
        "steps": [
            "{TOOL:TestTool(query='test')}",
            "{CODE:print('hello')}",
            "{SUMMARIZE}"
        ]
    })
    
    # 2. Summary generation
    summary_text = "Research complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),  # Plan (returns: text, usage, tier)
        (summary_text, {"tokens": 5}, "flash")  # Summary
    ]
    
    # Setup Tool responses
    mock_tools.list_tools.return_value = "TestTool"
    mock_tools.dispatch.return_value = {"result": "success"}
    
    # Run Orchestrator
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Test Goal")
    
    # Verify Plan
    assert len(evidence.tool_outputs) == 2
    assert "{TOOL:TestTool(query='test')}" in evidence.tool_outputs
    assert "{CODE:print('hello')}" in evidence.tool_outputs
    assert evidence.notes == [summary_text]
    
    # Verify LLM calls
    assert mock_llm.generate.call_count == 2
    
    # Verify Tool calls
    mock_tools.dispatch.assert_called_with("TestTool", query="test")
