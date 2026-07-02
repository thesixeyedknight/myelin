"""Reviewer agent for critiquing research plans."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from src.agent.llm import LLMClient
from src.utils.logging import LOGGER

def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = Path(f"prompts/{name}.md")
    if path.exists():
        return path.read_text()
    return ""

class ReviewerAgent:
    """Critiques research plans to ensure quality."""
    
    def __init__(self):
        self.llm = LLMClient()
    
    def review_plan(self, goal: str, plan: List[str]) -> Tuple[bool, str]:
        """
        Review a proposed plan.
        Returns: (is_approved, feedback)
        """
        LOGGER.log(event="reviewer_start", goal=goal)
        
        system_prompt = load_prompt("reviewer_system")
        user_prompt = (
            load_prompt("reviewer_user")
            .replace("{{goal}}", goal)
            .replace("{{plan_json}}", json.dumps(plan, indent=2))
        )
        
        # Use Pro tier for critical reasoning
        text, usage, tier = self.llm.generate(system_prompt, user_prompt, tier="pro")
        LOGGER.log(event="reviewer_end", usage=usage, tier=tier)
        
        # Parse JSON response
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
        
        try:
            data = json.loads(clean_text)
            status = data.get("status", "CHANGES NEEDED")
            feedback = data.get("feedback", "No feedback provided.")
            
            is_approved = status == "APPROVED"
            return is_approved, feedback
            
        except Exception as e:
            LOGGER.log(event="reviewer_parse_error", error=str(e))
            # Fallback: assume changes needed if parsing fails
            return False, f"Failed to parse reviewer response: {str(e)}"
