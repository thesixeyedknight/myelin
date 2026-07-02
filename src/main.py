from __future__ import annotations
import argparse
import json
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from src.agent.orchestrator import Orchestrator
from src.utils.logging import LOGGER
from src.configs.settings import SETTINGS

console = Console()


def parse_args():
    p = argparse.ArgumentParser(description="AI Research Automation – Minimal")
    p.add_argument("goal", type=str, help="Research objective")
    p.add_argument("--auto-approve", action="store_true", help="Run without interactive approvals")
    return p.parse_args()


def main():
    args = parse_args()
    
    console.print(Panel.fit(f"[bold blue]Myelin Research Agent[/bold blue]\nGoal: {args.goal}", title="Welcome"))
    console.print(f"[dim]Model: {SETTINGS.gemini_model}[/dim]")
    
    orch = Orchestrator(auto_approve=args.auto_approve)
    
    with console.status("[bold green]Running agent...[/bold green]", spinner="dots"):
        ev = orch.run(args.goal)
    
    console.print("\n[bold]=== SUMMARY NOTES ===[/bold]\n")
    for n in ev.notes:
        console.print(Panel(n, title="Note", border_style="blue"))
        
    LOGGER.log(event="done", evidence=ev.model_dump())
    console.print(f"\n[dim]Log written to {LOGGER.path}[/dim]")


if __name__ == "__main__":
    main()
