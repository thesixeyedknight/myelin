"""Minimal unit test for _substitute_variables method (no imports of tools)."""
import re
import pytest
from src.utils.logging import LOGGER


class MockOrchestrator:
    """Minimal orchestrator mock to test variable substitution logic."""
    
    def __init__(self):
        self.context = {}
        self.run_id = "test123"
    
    def _substitute_variables(self, kwargs: dict) -> dict:
        """Substitute variable placeholders in tool arguments.
        
        Supports two strategies:
        1. Explicit: {{ variable_name }} -> resolve from context
        2. Implicit: if value matches a context key, substitute it
        
        Args:
            kwargs: Tool arguments dictionary
            
        Returns:
            Updated kwargs with variables resolved
        """
        VAR_REGEX = re.compile(r"\{\{\s*([\w_]+)\s*\}\}")
        substituted = {}
        
        for key, value in kwargs.items():
            if not isinstance(value, str):
                substituted[key] = value
                continue
                
            # Strategy 1: Explicit {{ variable }} placeholders
            match = VAR_REGEX.search(value)
            if match:
                var_name = match.group(1)
                if var_name in self.context:
                    resolved_value = self.context[var_name]
                    substituted[key] = resolved_value
                    LOGGER.log(
                        event="variable_substituted",
                        run_id=self.run_id,
                        strategy="explicit",
                        variable=var_name,
                        value=resolved_value
                    )
                else:
                    LOGGER.log(
                        event="variable_not_found",
                        run_id=self.run_id,
                        variable=var_name,
                        available_keys=list(self.context.keys())
                    )
                    substituted[key] = value  # Keep original if not found
            # Strategy 2: Implicit key lookup
            elif value in self.context:
                resolved_value = self.context[value]
                substituted[key] = resolved_value
                LOGGER.log(
                    event="variable_substituted",
                    run_id=self.run_id,
                    strategy="implicit",
                    variable=value,
                    value=resolved_value
                )
            else:
                substituted[key] = value
                
        return substituted


def test_explicit_placeholder():
    """Test {{ variable }} substitution."""
    orch = MockOrchestrator()
    orch.context = {"output_file": "/tmp/test.txt"}
    
    kwargs = {"path": "{{ output_file }}"}
    result = orch._substitute_variables(kwargs)
    
    assert result["path"] == "/tmp/test.txt"


def test_implicit_lookup():
    """Test implicit key lookup."""
    orch = MockOrchestrator()
    orch.context = {"deg_file": "/work/results.csv"}
    
    kwargs = {"input": "deg_file"}
    result = orch._substitute_variables(kwargs)
    
    assert result["input"] == "/work/results.csv"


def test_literal_passthrough():
    """Test literal values pass through unchanged."""
    orch = MockOrchestrator()
    orch.context = {"something": "else"}
    
    kwargs = {"query": "SLE biomarkers", "limit": 10}
    result = orch._substitute_variables(kwargs)
    
    assert result["query"] == "SLE biomarkers"
    assert result["limit"] == 10


def test_missing_variable():
    """Test missing variables keep original value."""
    orch = MockOrchestrator()
    orch.context = {}
    
    kwargs = {"path": "{{ nonexistent }}"}
    result = orch._substitute_variables(kwargs)
    
    assert result["path"] == "{{ nonexistent }}"


def test_multiple_substitutions():
    """Test multiple variables in one call."""
    orch = MockOrchestrator()
    orch.context = {
        "file1": "/path/1.txt",
        "file2": "/path/2.txt"
    }
    
    kwargs = {
        "input1": "{{ file1 }}",
        "input2": "{{ file2 }}",
        "literal": "unchanged"
    }
    result = orch._substitute_variables(kwargs)
    
    assert result["input1"] == "/path/1.txt"
    assert result["input2"] == "/path/2.txt"
    assert result["literal"] == "unchanged"


def test_non_string_values():
    """Test that non-string values pass through unchanged."""
    orch = MockOrchestrator()
    orch.context = {"var": "value"}
    
    kwargs = {
        "count": 42,
        "enabled": True,
        "threshold": 0.05,
        "items": ["a", "b"]
    }
    result = orch._substitute_variables(kwargs)
    
    assert result == kwargs  # Should be unchanged
