import time
import json
import sys
from pathlib import Path
from src.agent.orchestrator import Orchestrator
from src.utils.logging import LOGGER

# Test Matrix
TESTS = [
    {
        "id": "UC1_L1",
        "name": "Lit Review - Simple",
        "prompt": "Search PubMed for 'CRISPR off-target' and summarize.",
        "expected_tools": ["PubMedSearch", "PubMedFetch"]
    },
    {
        "id": "UC1_L2",
        "name": "Lit Review - Complex",
        "prompt": "Search PubMed for 'CRISPR off-target 2024', extract rates, and plot histogram.",
        "expected_tools": ["PubMedSearch", "PubMedFetch", "run_python"]
    },
    {
        "id": "UC2_L1",
        "name": "Homology - Simple",
        "prompt": "Find PDB ID for human TP53.",
        "expected_tools": ["RCSBFindByGene"] # UniProtSearch is optional if model knows gene name
    },
    {
        "id": "UC3_L1",
        "name": "Data QC - Simple",
        "prompt": "List files in data/ directory.",
        "expected_tools": ["SafeShell"] # Model prefers shell for listing
    },
    {
        "id": "UC3_L2",
        "name": "Data QC - Complex",
        "prompt": "Parse .log files in data/, find 'Error rate: X%', and if X > 1.0, print the filename.",
        "expected_tools": ["run_python"]
    }
    # Add more as we go
]

def run_test(test_case):
    print(f"\n=== Running Test: {test_case['name']} ===")
    print(f"Prompt: {test_case['prompt']}")
    
    orch = Orchestrator(auto_approve=True)
    
    start_time = time.time()
    try:
        evidence = orch.run(test_case['prompt'])
        duration = time.time() - start_time
        
        # Verification
        tools_used = set()
        for step in evidence.tool_outputs.keys():
            if "{TOOL:" in step:
                name = step.split("{TOOL:")[1].split("(")[0]
                tools_used.add(name)
            elif "{CODE:" in step:
                tools_used.add("run_python")
        
        missing = [t for t in test_case.get("expected_tools", []) if t not in tools_used]
        
        print(f"Duration: {duration:.1f}s")
        print(f"Tools Used: {tools_used}")
        
        if missing:
            print(f"FAILED: Missing expected tools: {missing}")
            return False
        else:
            print("PASSED")
            return True
            
    except Exception as e:
        print(f"CRASHED: {e}")
        return False

def main():
    # Filter tests by arg if provided
    target = sys.argv[1] if len(sys.argv) > 1 else None
    
    results = {}
    for test in TESTS:
        if target and target not in test["id"]:
            continue
            
        success = run_test(test)
        results[test["id"]] = success
        
        # Enforce extra delay between tests to be safe with rate limits
        # The internal rate limiter handles the calls, but a buffer is good.
        print("Waiting 5s before next test...")
        time.sleep(5)

    print("\n=== Final Results ===")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
