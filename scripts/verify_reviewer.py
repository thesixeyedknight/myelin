"""Verify ReviewerAgent functionality."""
import json
from unittest.mock import MagicMock, patch
from src.agent.reviewer import ReviewerAgent

def test_reviewer():
    print("Testing ReviewerAgent...")
    
    goal = "Find the function of protein p53."
    plan_good = ["Search PubMed for p53", "Summarize findings"]
    plan_bad = ["Search Google"]
    
    # Mock LLMClient
    with patch("src.agent.reviewer.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        
        # Scenario 1: Good Plan
        mock_instance.generate.return_value = (
            '```json\n{"status": "APPROVED", "feedback": "Plan looks solid."}\n```',
            {"total_token_count": 50},
            "pro"
        )
        
        reviewer = ReviewerAgent()
        approved, feedback = reviewer.review_plan(goal, plan_good)
        
        print(f"\nScenario 1 (Good Plan): Approved={approved}, Feedback={feedback}")
        if approved:
            print("SUCCESS: Good plan approved.")
        else:
            print("FAILURE: Good plan rejected.")

        # Scenario 2: Bad Plan
        mock_instance.generate.return_value = (
            '```json\n{"status": "CHANGES NEEDED", "feedback": "Plan is too vague."}\n```',
            {"total_token_count": 50},
            "pro"
        )
        
        approved, feedback = reviewer.review_plan(goal, plan_bad)
        
        print(f"\nScenario 2 (Bad Plan): Approved={approved}, Feedback={feedback}")
        if not approved:
            print("SUCCESS: Bad plan rejected.")
        else:
            print("FAILURE: Bad plan approved.")

if __name__ == "__main__":
    test_reviewer()
