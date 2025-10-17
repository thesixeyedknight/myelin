from __future__ import annotations
import argparse, json, sys
from src.agent.orchestrator import Orchestrator
from src.utils.logging import LOGGER
from src.configs.settings import SETTINGS

def parse_args():
    p = argparse.ArgumentParser(description="AI Research Automation – Minimal")
    p.add_argument("goal", type=str, help="Research objective")
    p.add_argument("--auto-approve", action="store_true", help="Run without interactive approvals")
    p.add_argument("--verbose", action="store_true", help="Verbose logging (DEBUG to console)")
    p.add_argument("--save-llm", action="store_true", help="Save full LLM prompts/responses under logs/llm/")
    return p.parse_args()

def main():
    args = parse_args()
    # set logger level
    if args.verbose:
        LOGGER.set_level("DEBUG")
    else:
        LOGGER.set_level(SETTINGS.log_level)

    LOGGER.info(event="start", goal=args.goal, auto_approve=args.auto_approve,
                verbose=args.verbose, save_llm=args.save_llm)

    try:
        orch = Orchestrator(auto_approve=args.auto_approve, save_llm_io=args.save_llm)
        ev = orch.run(args.goal)
        print("\n=== SUMMARY NOTES ===\n")
        for n in ev.notes:
            print(n)
        LOGGER.info(event="done", evidence=ev.model_dump())
    except Exception as e:
        LOGGER.error(event="fatal", msg=str(e))
        print(f"\nERROR: {e}\nSee logs/run.jsonl and logs/llm/ for details.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
