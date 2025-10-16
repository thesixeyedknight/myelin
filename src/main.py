from __future__ import annotations
import argparse
import json
from src.agent.orchestrator import Orchestrator
from src.utils.logging import LOGGER


def parse_args():
    p = argparse.ArgumentParser(description="AI Research Automation – Minimal")
    p.add_argument("goal", type=str, help="Research objective")
    p.add_argument("--auto-approve", action="store_true", help="Run without interactive approvals")
    return p.parse_args()


def main():
    args = parse_args()
    orch = Orchestrator(auto_approve=args.auto_approve)
    ev = orch.run(args.goal)
    print("\n=== SUMMARY NOTES ===\n")
    for n in ev.notes:
        print(n)
    LOGGER.log(event="done", evidence=ev.model_dump())


if __name__ == "__main__":
    main()
