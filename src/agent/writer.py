"""Writer agent for generating structured research reports."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

from src.agent.llm import LLMClient
from src.utils.logging import LOGGER

def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = Path(f"prompts/{name}.md")
    if path.exists():
        return path.read_text()
    return ""

class WriterAgent:
    """Synthesizes research evidence into a structured report."""
    
    def __init__(self):
        self.llm = LLMClient()
    
    def write_report(self, goal: str, evidence: List[Dict[str, Any]]) -> str:
        """Generate a Markdown report based on the goal and collected evidence."""
        LOGGER.log(event="writer_start", goal=goal)
        
        system_prompt = load_prompt("writer_system")
        user_prompt = (
            load_prompt("writer_user")
            .replace("{{goal}}", goal)
            .replace("{{evidence_json}}", json.dumps(evidence, indent=2))
        )
        
        # Generate report using Pro tier for best quality, fallback to Flash
        text, usage, tier = self.llm.generate(system_prompt, user_prompt, tier="pro")
        
        LOGGER.log(event="writer_end", usage=usage, tier=tier)
        return text
