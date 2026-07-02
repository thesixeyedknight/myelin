"""Tests for orchestrator variable passing functionality."""
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.agent.orchestrator import Orchestrator
from src.utils.schema import Plan, Evidence


@pytest.fixture
def mock_llm():
    """Mock LLM client."""
    with patch("src.agent.orchestrator.LLMClient") as MockLLM:
        client = MockLLM.return_value
        yield client


@pytest.fixture
def mock_tools():
    """Mock tools registry."""
    with patch("src.agent.orchestrator.T") as MockTools:
        yield MockTools


def test_explicit_placeholder_substitution(mock_llm, mock_tools):
    """Test explicit {{ variable }} placeholder substitution."""
    # Setup plan
    plan_json = json.dumps({
        "steps": [
            "{TOOL:CreateFile(name='test.txt')}",
            "{TOOL:ReadFile(path='{{ output_file }}')}"
        ]
    })
    summary_text = "Complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]
    
    # Setup tool responses
    mock_tools.list_tools.return_value = "CreateFile, ReadFile"
    mock_tools.dispatch.side_effect = [
        {"output_file": "/tmp/test.txt", "success": True},  # CreateFile output
        {"content": "test content", "success": True}         # ReadFile output
    ]
    
    # Run orchestrator
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Create and read a file")
    
    # Verify tool calls
    assert mock_tools.dispatch.call_count == 2
    
    # First call: CreateFile with name='test.txt'
    first_call = mock_tools.dispatch.call_args_list[0]
    assert first_call[0][0] == "CreateFile"
    assert first_call[1]["name"] == "test.txt"
    
    # Second call: ReadFile with resolved path
    second_call = mock_tools.dispatch.call_args_list[1]
    assert second_call[0][0] == "ReadFile"
    assert second_call[1]["path"] == "/tmp/test.txt"  # Variable resolved!
    
    # Verify context was updated
    assert "output_file" in orch.context
    assert orch.context["output_file"] == "/tmp/test.txt"


def test_no_implicit_key_lookup(mock_llm, mock_tools):
    """Bare literal args must NOT be swapped just because they match a context key.

    Implicit lookup used to substitute any literal argument value that
    coincidentally matched a context key. Context keys come from flattening
    every tool's nested dict output (e.g. sample_groups={'SLE': 924}), so a
    plain literal like case_label='SLE' could silently turn into the
    unrelated int 924. Only explicit {{ variable }} placeholders resolve now.
    """
    plan_json = json.dumps({
        "steps": [
            "{TOOL:DiffExpression(expression_file='data.csv')}",
            "{TOOL:EnrichmentAnalysis(input='deg_file')}"
        ]
    })
    summary_text = "Complete."

    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]

    mock_tools.list_tools.return_value = "DiffExpression, EnrichmentAnalysis"
    mock_tools.dispatch.side_effect = [
        {
            "success": True,
            "deg_file": "/work/deg_results/deg_results.csv",
            "n_deg_total": 150
        },
        {"success": True, "pathways": ["pathway1", "pathway2"]}
    ]

    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Analyze differential expression")

    # Bare literal "deg_file" is passed through unchanged, not resolved
    second_call = mock_tools.dispatch.call_args_list[1]
    assert second_call[0][0] == "EnrichmentAnalysis"
    assert second_call[1]["input"] == "deg_file"


def test_no_substitution_with_literal_values(mock_llm, mock_tools):
    """Test that literal values pass through unchanged."""
    plan_json = json.dumps({
        "steps": [
            "{TOOL:SearchPubmed(query='SLE biomarkers')}"
        ]
    })
    summary_text = "Complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]
    
    mock_tools.list_tools.return_value = "SearchPubmed"
    mock_tools.dispatch.return_value = {"articles": [], "count": 0}
    
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Search literature")
    
    # Verify literal value unchanged
    call = mock_tools.dispatch.call_args_list[0]
    assert call[1]["query"] == "SLE biomarkers"


def test_missing_variable_handling(mock_llm, mock_tools):
    """Test graceful handling of missing variables."""
    plan_json = json.dumps({
        "steps": [
            "{TOOL:ReadFile(path='{{ nonexistent }}')}"
        ]
    })
    summary_text = "Complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]
    
    mock_tools.list_tools.return_value = "ReadFile"
    mock_tools.dispatch.return_value = {"error": "File not found"}
    
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Read a file")
    
    # Verify original value passed (not resolved)
    call = mock_tools.dispatch.call_args_list[0]
    assert call[1]["path"] == "{{ nonexistent }}"  # Unchanged


def test_nested_dict_flattening(mock_llm, mock_tools):
    """Test that nested dictionaries are flattened into context."""
    plan_json = json.dumps({
        "steps": [
            "{TOOL:ComplexTool(param='value')}",
            "{TOOL:UseTool(input='{{ nested_key }}')}"
        ]
    })
    summary_text = "Complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]
    
    mock_tools.list_tools.return_value = "ComplexTool, UseTool"
    mock_tools.dispatch.side_effect = [
        {
            "success": True,
            "result": {
                "nested_key": "/path/to/file.txt",
                "other": "value"
            }
        },
        {"success": True}
    ]
    
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Test nested output")
    
    # Verify nested value was flattened and accessible
    assert "nested_key" in orch.context
    assert orch.context["nested_key"] == "/path/to/file.txt"
    
    # Verify it was used in second tool
    second_call = mock_tools.dispatch.call_args_list[1]
    assert second_call[1]["input"] == "/path/to/file.txt"


def test_context_persistence_across_steps(mock_llm, mock_tools):
    """Test that context persists and accumulates across multiple steps."""
    plan_json = json.dumps({
        "steps": [
            "{TOOL:Step1()}",
            "{TOOL:Step2()}",
            "{TOOL:Step3(file1='{{ var1 }}', file2='{{ var2 }}')}"
        ]
    })
    summary_text = "Complete."
    
    mock_llm.generate.side_effect = [
        (plan_json, {"tokens": 10}, "flash"),
        (summary_text, {"tokens": 5}, "flash")
    ]
    
    mock_tools.list_tools.return_value = "Step1, Step2, Step3"
    mock_tools.dispatch.side_effect = [
        {"var1": "file1.txt"},
        {"var2": "file2.txt"},
        {"success": True}
    ]
    
    orch = Orchestrator(auto_approve=True)
    evidence = orch.run("Multi-step workflow")
    
    # Verify both variables available in final step
    third_call = mock_tools.dispatch.call_args_list[2]
    assert third_call[1]["file1"] == "file1.txt"
    assert third_call[1]["file2"] == "file2.txt"
