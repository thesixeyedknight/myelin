"""Hierarchical orchestration for complex research tasks."""
from __future__ import annotations
import json
import uuid
from typing import Dict, List, Any
from pathlib import Path

from src.agent.llm import LLMClient
from src.agent.orchestrator import Orchestrator, Evidence
from src.agent.writer import WriterAgent
from src.agent.reviewer import ReviewerAgent
from src.tools import registry as T
from src.utils.logging import LOGGER


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = Path(f"prompts/{name}.md")
    if path.exists():
        return path.read_text()
    return ""


class DirectorAgent:
    """Plans subtasks for complex research goals."""
    
    def __init__(self):
        self.llm = LLMClient()
        self.run_id = str(uuid.uuid4())[:8]
    
    def decompose(self, goal: str) -> List[str]:
        """Break down complex goal into subtasks."""
        tools = T.list_tools()
        system_prompt = load_prompt("director_system")
        user_prompt = (
            load_prompt("director_user")
            .replace("{{goal}}", goal)
            .replace("{{tools}}", tools)
        )
        
        LOGGER.log(event="director_decompose_start", run_id=self.run_id, goal=goal)
        text, usage, tier = self.llm.generate(system_prompt, user_prompt, tier="lite")
        LOGGER.log(event="director_decompose_end", run_id=self.run_id, usage=usage, tier=tier)
        
        # Parse JSON response
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
        
        try:
            data = json.loads(clean_text)
            subtasks = data.get("subtasks", [])
            LOGGER.log(event="director_subtasks", run_id=self.run_id, subtasks=subtasks)
            return subtasks
        except Exception as e:
            LOGGER.log(event="director_parse_error", run_id=self.run_id, error=str(e))
            # Fallback: single-task execution
            return [goal]


class WorkerAgent:
    """Executes individual subtasks."""
    
    def __init__(self):
        self.orchestrator = Orchestrator(auto_approve=True)
    
    def execute(self, subtask: str, context: Dict[str, Any]) -> Evidence:
        """Execute a single subtask with context from previous steps."""
        LOGGER.log(event="worker_start", subtask=subtask)
        
        # Worker uses the standard orchestrator for execution
        evidence = self.orchestrator.run(subtask)
        
        LOGGER.log(event="worker_end", subtask=subtask, citations=len(evidence.citations))
        return evidence


class HierarchicalOrchestrator:
    """Coordinates Director and Worker agents."""
    
    def __init__(self):
        self.director = DirectorAgent()
        self.worker = WorkerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
        self.run_id = str(uuid.uuid4())[:8]
    
    def run(self, goal: str) -> Dict[str, Any]:
        """Execute complex goal using hierarchical planning."""
        LOGGER.log(event="hierarchical_start", run_id=self.run_id, goal=goal)
        
        # Step 1: Director decomposes goal (with Reviewer loop)
        current_goal = goal
        subtasks = []
        max_retries = 3
        
        for attempt in range(max_retries):
            subtasks = self.director.decompose(current_goal)
            
            # Review the plan
            approved, feedback = self.reviewer.review_plan(goal, subtasks)
            
            if approved:
                LOGGER.log(event="plan_approved", run_id=self.run_id, attempt=attempt)
                break
            
            LOGGER.log(event="plan_rejected", run_id=self.run_id, attempt=attempt, feedback=feedback)
            # Update goal with feedback for next iteration
            current_goal = f"{goal}\n\nIMPORTANT: The previous plan was rejected. Feedback: {feedback}\nPlease revise the plan."
        else:
            LOGGER.log(event="plan_max_retries", run_id=self.run_id)
            # Proceed with last plan anyway or fail? Let's proceed with warning.
            pass
        
        # Step 2: Worker executes subtasks sequentially
        all_evidence = []
        shared_context = {}
        
        for i, subtask in enumerate(subtasks):
            LOGGER.log(event="subtask_start", run_id=self.run_id, index=i, subtask=subtask)
            evidence = self.worker.execute(subtask, shared_context)
            all_evidence.append({
                "subtask": subtask,
                "evidence": evidence.model_dump()
            })
            
            # Update shared context with outputs from this subtask
            shared_context[f"subtask_{i}"] = evidence.tool_outputs
        
        LOGGER.log(event="hierarchical_end", run_id=self.run_id, subtasks_completed=len(subtasks))
        
        # Step 3: Writer generates report
        report = self.writer.write_report(goal, all_evidence)
        
        # Save report to file
        report_path = Path("work/report.md")
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report)
        
        return {
            "goal": goal,
            "subtasks": subtasks,
            "evidence": all_evidence,
            "report": report,
            "run_id": self.run_id
        }
