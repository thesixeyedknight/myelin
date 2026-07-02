"""Test hierarchical planning."""
import sys
sys.path.insert(0, ".")

import pytest
from src.agent.hierarchical import HierarchicalOrchestrator
from src.configs.settings import SETTINGS
import json

@pytest.mark.skipif(not SETTINGS.gemini_api_key, reason="API key required")
@pytest.mark.integration
def test_complex_query():
    """Test with a multi-step research query."""
    print("=== Testing Hierarchical Planning ===\n")
    
    orchestrator = HierarchicalOrchestrator()
    
    goal = "Compare CRISPR off-target rates in 2023 vs 2024"
    
    print(f"Goal: {goal}\n")
    print("Running hierarchical orchestration...\n")
    
    result = orchestrator.run(goal)
    
    print(f"✓ Completed with {len(result['subtasks'])} subtasks:\n")
    for i, subtask in enumerate(result['subtasks'], 1):
        print(f"  {i}. {subtask}")
    
    print(f"\n✓ Evidence collected from {len(result['evidence'])} subtasks")
    print(f"\nFull output saved to work/hierarchical_output.json\n")
    
    # Save detailed output
    with open("work/hierarchical_output.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

if __name__ == "__main__":
    test_complex_query()
