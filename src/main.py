from __future__ import annotations
import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from src.agent.orchestrator import Orchestrator
from src.utils.logging import LOGGER
from src.configs.settings import SETTINGS

console = Console()


def parse_args():
    p = argparse.ArgumentParser(description="AI Research Automation – Minimal")
    p.add_argument("goal", type=str, help="Research objective")
    p.add_argument("--auto-approve", action="store_true", help="Run without interactive approvals")
    p.add_argument("--verbose", action="store_true", help="Verbose logging (DEBUG to console)")
    p.add_argument("--save-llm", action="store_true", help="Save full LLM prompts/responses under logs/llm/")
    return p.parse_args()


def main():
    args = parse_args()

    LOGGER.set_level("DEBUG" if args.verbose else SETTINGS.log_level)

    console.print(Panel.fit(f"[bold blue]Myelin Research Agent[/bold blue]\nGoal: {args.goal}", title="Welcome"))
    console.print(f"[dim]Model: {SETTINGS.gemini_model}[/dim]")

    LOGGER.info(event="start", goal=args.goal, auto_approve=args.auto_approve,
                verbose=args.verbose, save_llm=args.save_llm)

    try:
        orch = Orchestrator(auto_approve=args.auto_approve, save_llm_io=args.save_llm)

        with console.status("[bold green]Running agent...[/bold green]", spinner="dots"):
            ev = orch.run(args.goal)

        console.print("\n[bold]=== SUMMARY NOTES ===[/bold]\n")
        for n in ev.notes:
            console.print(Panel(n, title="Note", border_style="blue"))

        LOGGER.info(event="done", evidence=ev.model_dump())
        console.print(f"\n[dim]Log written to {LOGGER.path}[/dim]")
    except Exception as e:
        LOGGER.error(event="fatal", msg=str(e))
        console.print(f"\n[bold red]ERROR:[/bold red] {e}")
        console.print("[dim]See logs/run.jsonl and logs/llm/ for details.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
