from __future__ import annotations
import json
import re
import uuid
from pathlib import Path
from src.utils.logging import LOGGER
from src.utils.schema import Plan, Evidence
from src.configs.settings import SETTINGS
from src.agent.llm import LLMClient
from src.tools import registry as T
from src.sandbox.runner import run_python

PROMPTS = {
    "plan_system": Path("prompts/plan_system.md").read_text(),
    "plan_user": Path("prompts/plan_user.md").read_text(),
    "sum_system": Path("prompts/summarize_system.md").read_text(),
    "sum_user": Path("prompts/summarize_user.md").read_text(),
}

# Regex for parsing tool calls: {TOOL:Name(args)}
TOOL_REGEX = re.compile(r"\{TOOL:(\w+)\((.*)\)\}")
# Regex for parsing code blocks: {CODE: ... }
CODE_REGEX = re.compile(r"\{CODE:(.*)\}", re.DOTALL)


class Orchestrator:
    def __init__(self, auto_approve: bool = False):
        self.llm = LLMClient()
        self.auto = auto_approve
        self.run_id = str(uuid.uuid4())[:8]
        self.context = {}  # Variable context for multi-step workflows

    def plan(self, goal: str) -> Plan:
        tools = T.list_tools()
        u = (
            PROMPTS["plan_user"]
            .replace("{{goal}}", goal)
            .replace("{{file_list}}", "(see data/)")
            .replace("{{prefs}}", "")
        )
        s = PROMPTS["plan_system"] + f"\nAvailable tools: {tools}"
        
        LOGGER.log(event="plan_start", run_id=self.run_id, goal=goal)
        text, usage, tier = self.llm.generate(s, u, tier="flash")
        LOGGER.log(event="plan_generated", run_id=self.run_id, usage=usage)
        
        # Clean up markdown code blocks
        clean_text = text.strip()
        if clean_text.startswith("```"):
            # Remove opening ```json or ```
            clean_text = re.sub(r"^```\w*\s*", "", clean_text)
            # Remove closing ```
            clean_text = re.sub(r"\s*```$", "", clean_text)
        
        try:
            data = json.loads(clean_text)
            return Plan(**data)
        except Exception as e:
            LOGGER.log(event="plan_parse_error", run_id=self.run_id, error=str(e), raw_text=text)
            # Fallback: naive 3-step plan if the model responded prose-only
            return Plan(steps=["{TOOL:PubMedSearch(term)}", "{TOOL:PubMedFetch(pmids)}", "{SUMMARIZE}"])

    def approve(self, step: str) -> bool:
        if self.auto:
            return True
        print(f"Proposed step: {step}")
        resp = input("Proceed? [y/N] ").strip().lower()
        return resp == "y"

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

    def run_step(self, step: str, evidence: Evidence):
        try:
            # 1. Handle Tool Calls
            tool_match = TOOL_REGEX.match(step)
            if tool_match:
                name = tool_match.group(1)
                args_str = tool_match.group(2)
                
                kwargs = {}
                if args_str:
                    # Naive parsing of key=value, fallback to query string
                    # This is still simple but slightly more robust than split(',')
                    if "=" in args_str:
                        try:
                            # Try to parse as k=v pairs
                            for kv in args_str.split(","):
                                if "=" in kv:
                                    k, v = kv.split("=", 1)
                                    kwargs[k.strip()] = v.strip().strip("'\"")
                                else:
                                    # If mixed, just treat as query? Or ignore?
                                    pass
                        except Exception:
                            kwargs["query"] = args_str.strip().strip("'\"")
                    else:
                        kwargs["query"] = args_str.strip().strip("'\"")

                # Substitute variables before dispatching
                kwargs = self._substitute_variables(kwargs)
                
                LOGGER.log(event="tool_start", run_id=self.run_id, tool=name, args=kwargs)
                out = T.dispatch(name, **kwargs)
                evidence.tool_outputs[step] = out
                
                # Update context with output values
                if isinstance(out, dict):
                    # Add top-level keys to context
                    for k, v in out.items():
                        if isinstance(v, (str, int, float, bool)):
                            self.context[k] = v
                        # Flatten one level for nested dicts
                        elif isinstance(v, dict):
                            for nested_k, nested_v in v.items():
                                if isinstance(nested_v, (str, int, float, bool)):
                                    self.context[nested_k] = nested_v
                    LOGGER.log(
                        event="context_updated",
                        run_id=self.run_id,
                        context_keys=list(self.context.keys())
                    )
                
                # Special handling for PubMed to collect citations
                if name.startswith("PubMed") and "articles" in out:
                    for a in out["articles"]:
                        evidence.citations.append(a["pmid"])
                
                LOGGER.log(event="tool_end", run_id=self.run_id, tool=name, output=out)
                
                # Save output to work/last_tool_output.json for the sandbox
                work_dir = Path("work")
                work_dir.mkdir(exist_ok=True)
                try:
                    with open(work_dir / "last_tool_output.json", "w") as f:
                        json.dump(out, f, indent=2)
                except Exception as e:
                    LOGGER.log(event="save_output_error", error=str(e))
                
                return out

            # 2. Handle Code Execution
            code_match = CODE_REGEX.match(step)
            if code_match:
                code = code_match.group(1).strip()
                # Remove "python" language identifier if present (with optional colon)
                code = re.sub(r"^python:?\s*", "", code, flags=re.IGNORECASE)
                
                LOGGER.log(event="code_start", run_id=self.run_id)
                res = run_python(code)
                evidence.tool_outputs[step] = res
                
                if res.get("stderr"):
                    LOGGER.log(event="code_error", run_id=self.run_id, step=step, stderr=res["stderr"])
                else:
                    LOGGER.log(event="code_ok", run_id=self.run_id, step=step, stdout=res["stdout"])
                return res

            # 3. Handle Summarization
            if step == "{SUMMARIZE}":
                s = PROMPTS["sum_system"]
                u = PROMPTS["sum_user"].replace("{{evidence_json}}", json.dumps(evidence.model_dump())).replace(
                    "{{open_questions}}", ""
                )
                LOGGER.log(event="summary_start", run_id=self.run_id)
                text, usage, tier = self.llm.generate(s, u, tier="flash")
                evidence.notes.append(text)
                LOGGER.log(event="summary_end", run_id=self.run_id, text=text, usage=usage)
                return text

            LOGGER.log(event="step_skip", run_id=self.run_id, step=step)
            return None

        except Exception as e:
            LOGGER.log(event="step_error", run_id=self.run_id, step=step, error=str(e))
            return {"error": str(e)}

    def run(self, goal: str) -> Evidence:
        try:
            plan = self.plan(goal)
            LOGGER.log(event="plan_final", run_id=self.run_id, plan=plan.model_dump())
            print("Plan:\n", json.dumps(plan.model_dump(), indent=2))
            
            evidence = Evidence()
            for step in plan.steps:
                if not self.approve(step):
                    print("Skipped step.")
                    LOGGER.log(event="step_rejected", run_id=self.run_id, step=step)
                    continue
                self.run_step(step, evidence)
            return evidence
        except Exception as e:
            LOGGER.log(event="run_fatal_error", run_id=self.run_id, error=str(e))
            print(f"Fatal error: {e}")
            return Evidence()
