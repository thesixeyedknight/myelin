from __future__ import annotations
import json
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


class Orchestrator:
    def __init__(self, auto_approve: bool = False):
        self.llm = LLMClient()
        self.auto = auto_approve

    def plan(self, goal: str) -> Plan:
        tools = T.list_tools()
        u = (
            PROMPTS["plan_user"]
            .replace("{{goal}}", goal)
            .replace("{{file_list}}", "(see data/)")
            .replace("{{prefs}}", "")
        )
        s = PROMPTS["plan_system"] + f"\nAvailable tools: {tools}"
        text, usage = self.llm.generate(s, u)
        LOGGER.log(event="plan_usage", usage=usage)
        try:
            data = json.loads(text)
            return Plan(**data)
        except Exception:
            # Fallback: naive 3-step plan if the model responded prose-only
            return Plan(steps=["{TOOL:PubMedSearch(term)}", "{TOOL:PubMedFetch(pmids)}", "{SUMMARIZE}"])

    def approve(self, step: str) -> bool:
        if self.auto:
            return True
        print(f"Proposed step: {step}")
        resp = input("Proceed? [y/N] ").strip().lower()
        return resp == "y"

    def run_step(self, step: str, evidence: Evidence):
        if step.startswith("{TOOL:"):
            name_args = step[len("{TOOL:") : -1]
            name, rest = name_args.split("(", 1)
            rest = rest[:-1] if rest.endswith(")") else rest
            kwargs = {}
            if rest:
                if "=" in rest:
                    for kv in rest.split(","):
                        k, v = kv.split("=", 1)
                        kwargs[k.strip()] = v.strip().strip("'\"")
                else:
                    kwargs["query"] = rest.strip().strip("'\"")
            out = T.dispatch(name, **kwargs)
            evidence.tool_outputs[step] = out
            if name.startswith("PubMed") and "articles" in out:
                for a in out["articles"]:
                    evidence.citations.append(a["pmid"])  # collect PMIDs
            LOGGER.log(event="tool", step=step, output=out)
            return out

        elif step.startswith("{CODE:"):
            code = step[len("{CODE:") : -1]
            res = run_python(code)
            evidence.tool_outputs[step] = res
            if res.get("stderr"):
                LOGGER.log(event="code_error", step=step, stderr=res["stderr"])
            else:
                LOGGER.log(event="code_ok", step=step, stdout=res["stdout"])
            return res

        elif step == "{SUMMARIZE}":
            s = PROMPTS["sum_system"]
            u = PROMPTS["sum_user"].replace("{{evidence_json}}", json.dumps(evidence.model_dump())).replace(
                "{{open_questions}}", ""
            )
            text, usage = self.llm.generate(s, u)
            evidence.notes.append(text)
            LOGGER.log(event="summary", text=text, usage=usage)
            return text

        else:
            LOGGER.log(event="skip", step=step)
            return None

    def run(self, goal: str) -> Evidence:
        plan = self.plan(goal)
        LOGGER.log(event="plan", plan=plan.model_dump())
        print("Plan:\n", json.dumps(plan.model_dump(), indent=2))
        evidence = Evidence()
        for step in plan.steps:
            if not self.approve(step):
                print("Skipped step.")
                continue
            self.run_step(step, evidence)
        return evidence
