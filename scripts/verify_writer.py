"""Verify WriterAgent functionality."""
import json
from unittest.mock import MagicMock, patch
from src.agent.writer import WriterAgent

def test_writer():
    print("Testing WriterAgent...")
    
    # Mock evidence
    goal = "Find the function of protein p53."
    evidence = [
        {
            "subtask": "Search for p53 function",
            "evidence": {
                "tool_outputs": {
                    "{TOOL:PubMedSearch(p53 function)}": {"articles": [{"pmid": "12345", "title": "p53 is a tumor suppressor"}]}
                },
                "citations": ["12345"],
                "notes": ["p53 is known as the guardian of the genome."]
            }
        }
    ]
    
    # Mock LLMClient
    with patch("src.agent.writer.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.generate.return_value = (
            "# Research Report\n\n## Executive Summary\np53 is a tumor suppressor.\n\n## References\n[PMID: 12345]",
            {"total_token_count": 100},
            "pro"
        )
        
        writer = WriterAgent()
        report = writer.write_report(goal, evidence)
        
        print("\nGenerated Report:\n")
        print(report)
        
        if "p53" in report and "12345" in report:
            print("\nSUCCESS: Report contains expected keywords and citations.")
        else:
            print("\nFAILURE: Report missing keywords or citations.")

if __name__ == "__main__":
    test_writer()
