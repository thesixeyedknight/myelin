from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List
import ast

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

_ALLOWED_PREFIXES = ("{TOOL:", "{CODE:", "{SUMMARIZE}")


def _q(v: Any) -> str:
    """Quote kwargs safely for canonical step strings."""
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, list):
        return "[" + ",".join(_q(x) for x in v) + "]"
    if v is None:
        return "None"
    return str(v)


def _normalize_steps(raw_steps: List[Any]) -> List[str]:
    """
    Accepts planner steps as strings or dicts like:
      {"TOOL":"PubMedSearch","query":"...", "retmax":5, ...}
      {"CODE":"print('hi')"}
      {"SUMMARIZE": null}
    and converts them to our canonical string format.
    """
    out: List[str] = []
    for s in raw_steps:
        if isinstance(s, str):
            out.append(s)
            continue
        if isinstance(s, dict):
            if "TOOL" in s:
                name = s["TOOL"]
                args = {k: v for k, v in s.items() if k != "TOOL"}
                argstr = ",".join(f"{k}={_q(v)}" for k, v in args.items())
                out.append(f"{{TOOL:{name}({argstr})}}")
                continue
            if "CODE" in s:
                out.append("{CODE:" + str(s["CODE"]) + "}")
                continue
            if "SUMMARIZE" in s:
                out.append("{SUMMARIZE}")
                continue
            raise ValueError(f"Unknown step object keys: {list(s.keys())}")
        raise ValueError(f"Step must be string or object, got: {type(s).__name__}")
    return out


def _validate_plan_object(obj: Dict[str, Any]) -> Plan:
    # First ensure the 'steps' exist and normalize to strings
    steps = obj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Planner returned no steps")

    steps_str = _normalize_steps(steps)

    # Reject common bad placeholders explicitly
    for s in steps_str:
        if not any(s.startswith(p) for p in _ALLOWED_PREFIXES):
            raise ValueError(f"Illegal step format: {s}")

        # Only inspect placeholders on TOOL steps
        if s.startswith("{TOOL:"):
            if 'pmids=["12345"]' in s or "term)" in s:
                raise ValueError(f"Placeholder or dummy arguments in TOOL step: {s}")

        # Hard rule: CODE must not call tools
        if s.startswith("{CODE:"):
            if "PubMedSearch(" in s or "PubMedFetch(" in s or "{TOOL:" in s:
                raise ValueError("CODE must not call tools; use TOOL steps.")
        if s.startswith("{CODE:") and "$LAST_" in s:
            raise ValueError("CODE must not use $LAST_* placeholders; use {SUMMARIZE} to consume evidence.")

    # Replace in object so Pydantic Plan can validate
    obj = dict(obj)
    obj["steps"] = steps_str
    return Plan(**obj)

def _split_kwargs(s: str) -> list[str]:
    """Split a kwarg string on top-level commas only (ignore commas in [], (), {}, or quotes)."""
    out, buf = [], []
    depth = 0
    in_q = None  # "'" or '"'
    i = 0
    while i < len(s):
        ch = s[i]
        if in_q:
            if ch == "\\":
                buf.append(ch)
                i += 1
                if i < len(s):
                    buf.append(s[i])
            elif ch == in_q:
                in_q = None
                buf.append(ch)
            else:
                buf.append(ch)
        else:
            if ch in ("'", '"'):
                in_q = ch
                buf.append(ch)
            elif ch in "([{":
                depth += 1
                buf.append(ch)
            elif ch in ")]}":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                token = "".join(buf).strip()
                if token:
                    out.append(token)
                buf = []
            else:
                buf.append(ch)
        i += 1
    token = "".join(buf).strip()
    if token:
        out.append(token)
    return out

def _parse_tool(step: str):
    # step like: {TOOL:Name(k=v,k2=v2)}
    name_args = step[len("{TOOL:") : -1]
    if "(" not in name_args:
        raise ValueError(f"Malformed TOOL step (no paren): {step}")
    name, rest = name_args.split("(", 1)
    rest = rest[:-1] if rest.endswith(")") else rest
    kwargs: Dict[str, Any] = {}
    if rest.strip():
        for kv in _split_kwargs(rest):
            k, v = kv.split("=", 1)
            v_str = v.strip()

            # strings
            if (v_str.startswith("'") and v_str.endswith("'")) or (v_str.startswith('"') and v_str.endswith('"')):
                v_parsed = v_str[1:-1].replace("\\'", "'").replace('\\\\', '\\')

            # booleans
            elif v_str in {"True", "true", "TRUE", "False", "false", "FALSE"}:
                v_parsed = v_str.lower() == "true"

            # list literals like ['123','456']
            elif v_str.startswith("[") and v_str.endswith("]"):
                try:
                    v_parsed = ast.literal_eval(v_str)
                except Exception:
                    raise ValueError(f"Could not parse list literal in TOOL step: {v_str}")

            # ints (best-effort)
            else:
                try:
                    v_parsed = int(v_str)
                except Exception:
                    v_parsed = v_str

            kwargs[k.strip()] = v_parsed
    return name.strip(), kwargs


def _precheck_tool_call(name: str, kwargs: Dict[str, Any]):
    """Hard-stop on missing required args; no auto-fix to keep debugging honest."""
    if name == "PubMedSearch":
        if "query" not in kwargs or not str(kwargs["query"]).strip():
            raise ValueError("Planner omitted required arg: PubMedSearch.query")
    if name == "PubMedFetch":
        pmids = kwargs.get("pmids")
        # Allow explicit placeholder; resolve later
        if pmids == "$LAST_PMIDS":
            return
        if not isinstance(pmids, list) or not pmids:
            raise ValueError("Planner omitted required arg: PubMedFetch.pmids (list[str] or '$LAST_PMIDS')")
        if not all(isinstance(x, str) and x.isdigit() for x in pmids):
            raise ValueError("Planner must pass PubMedFetch.pmids as list[str] of numeric PMIDs (or '$LAST_PMIDS').")
    if name == "BlastPoll":
        if "rid" not in kwargs or not str(kwargs["rid"]).strip():
            raise ValueError("Planner omitted required arg: BlastPoll.rid")
    if name == "RCSBFindByGene":
        # ---- alias common synonyms from LLM plans ----
        if "gene_name" in kwargs and "gene" not in kwargs:
            kwargs["gene"] = kwargs.pop("gene_name")
        if "max_hits" in kwargs and "rows" not in kwargs:
            try:
                kwargs["rows"] = int(kwargs.pop("max_hits"))
            except Exception:
                raise ValueError("RCSBFindByGene.max_hits must be an integer")
        
        # Defaults and allowed keys
        kwargs.setdefault("rows", 10)
        kwargs.setdefault("experimental_only", True)
        allowed = {"gene", "organism", "rows", "experimental_only"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f"Unknown kwargs for RCSBFindByGene: {sorted(unknown)}")

        for r in ("gene", "organism"):
            if r not in kwargs or not str(kwargs[r]).strip():
                raise ValueError(f"Missing required kwarg for RCSBFindByGene: {r}")

    if name == "UniProtSearch":
        # Map synonyms → canonical
        if "retmax" in kwargs and "size" not in kwargs:
            try:
                kwargs["size"] = int(kwargs.pop("retmax"))
            except Exception:
                raise ValueError("UniProtSearch.retmax must be an integer")
        if "max_hits" in kwargs and "size" not in kwargs:
            try:
                kwargs["size"] = int(kwargs.pop("max_hits"))
            except Exception:
                raise ValueError("UniProtSearch.max_hits must be an integer")
        kwargs.setdefault("size", 10)
        allowed = {"query", "size"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f"Unknown kwargs for UniProtSearch: {sorted(unknown)}")
        if "query" not in kwargs or not str(kwargs["query"]).strip():
            raise ValueError("Missing required kwarg for UniProtSearch: query")   


class Orchestrator:
    def __init__(self, auto_approve: bool = False, save_llm_io: bool | None = None):
        self.llm = LLMClient(save_io=save_llm_io)
        self.auto = auto_approve
        self.goal = ""

    def plan(self, goal: str) -> Plan:
        self.goal = goal
        tools = T.list_tools()
        u = (
            PROMPTS["plan_user"]
            .replace("{{goal}}", goal)
            .replace("{{file_list}}", "(see data/)")
            .replace("{{prefs}}", "")
        )
        s = PROMPTS["plan_system"] + f"\nAvailable tools: {tools}"
        LOGGER.info(event="plan_prompt_ready")
        text, usage = self.llm.generate(s, u, response_mime_type="application/json", tag="plan")
        LOGGER.debug(event="plan_raw_text", text=text[:2000])
        try:
            obj = json.loads(text)
        except Exception as e:
            LOGGER.error(event="plan_json_decode_failed", msg=str(e))
            raise RuntimeError("Planner did not return valid JSON. See logs/llm/* for raw output.") from e
        plan = _validate_plan_object(obj)
        return plan

    def approve(self, step: str) -> bool:
        if self.auto:
            return True
        print(f"Proposed step: {step}")
        resp = input("Proceed? [y/N] ").strip().lower()
        return resp == "y"

    def run_step(self, step: str, evidence: Evidence):
        LOGGER.info(event="step_start", step=step)
        if step.startswith("{TOOL:"):
            name, kwargs = _parse_tool(step)
            _precheck_tool_call(name, kwargs)
            if name == "PubMedFetch":
                # Resolve placeholder
                if kwargs.get("pmids") == "$LAST_PMIDS":
                    last_pmids = None
                    for k, v in reversed(list(evidence.tool_outputs.items())):
                        if k.startswith("{TOOL:PubMedSearch"):
                            last_pmids = v.get("pmids")
                            break
                    if not last_pmids:
                        raise ValueError("No prior PubMedSearch output to fill $LAST_PMIDS.")
                    kwargs["pmids"] = last_pmids

                # Strict binding: fetched PMIDs must match last search exactly
                last_pmids = None
                for k, v in reversed(list(evidence.tool_outputs.items())):
                    if k.startswith("{TOOL:PubMedSearch"):
                        last_pmids = v.get("pmids")
                        break
                if last_pmids and kwargs.get("pmids") != last_pmids:
                    raise ValueError(
                        f"PubMedFetch.pmids must match previous PubMedSearch.\n"
                        f"Got: {kwargs.get('pmids')}\nPrev: {last_pmids}"
                    )
            LOGGER.debug(event="tool_call", name=name, kwargs=kwargs)
            out = T.dispatch(name, **kwargs)
            evidence.tool_outputs[step] = out
            if name.startswith("PubMed") and "articles" in out:
                for a in out["articles"]:
                    evidence.citations.append(a["pmid"])
            LOGGER.info(event="tool_result", name=name, preview=str(out)[:600])
            return out

        elif step.startswith("{CODE:"):
            code = step[len("{CODE:") : -1]
            res = run_python(code)
            evidence.tool_outputs[step] = res
            level = "ERROR" if res.get("stderr") else "INFO"
            LOGGER.log(level, event="code_result",
                       returncode=res.get("returncode"),
                       stdout=res.get("stdout", "")[:600],
                       stderr=res.get("stderr", "")[:600])
            return res

        elif step == "{SUMMARIZE}":
            s = PROMPTS["sum_system"]
            u = PROMPTS["sum_user"].replace(
                "{{evidence_json}}", json.dumps(evidence.model_dump())
            ).replace("{{open_questions}}", "")
            text, usage = self.llm.generate(s, u, tag="summary")
            evidence.notes.append(text)
            LOGGER.info(event="summary_done", preview=text[:600])
            return text

        else:
            raise ValueError(f"Unknown step kind: {step}")

    def run(self, goal: str) -> Evidence:
        plan = self.plan(goal)
        LOGGER.info(event="plan_ok", plan=plan.model_dump())
        print("Plan:\n", json.dumps(plan.model_dump(), indent=2))
        evidence = Evidence()
        for step in plan.steps:
            if not self.approve(step):
                print("Skipped step.")
                LOGGER.info(event="step_skipped", step=step)
                continue
            self.run_step(step, evidence)
            LOGGER.info(event="step_end", step=step)
        return evidence
