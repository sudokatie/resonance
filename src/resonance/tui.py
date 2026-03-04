"""Interactive TUI for manual metric entry."""

from __future__ import annotations

from datetime import date
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, FloatPrompt, Confirm
from rich.table import Table
from rich.panel import Panel

from .database import Database
from .ingest.manual import log_metric, get_today_entries, delete_entry

console = Console()

# Common metrics with their typical ranges
COMMON_METRICS = {
    "mood": {"min": 1, "max": 10, "desc": "Overall mood (1-10)"},
    "energy": {"min": 1, "max": 10, "desc": "Energy level (1-10)"},
    "sleep": {"min": 0, "max": 12, "desc": "Hours of sleep"},
    "stress": {"min": 1, "max": 10, "desc": "Stress level (1-10)"},
    "focus": {"min": 1, "max": 10, "desc": "Focus/productivity (1-10)"},
    "exercise": {"min": 0, "max": 180, "desc": "Minutes of exercise"},
    "water": {"min": 0, "max": 20, "desc": "Glasses of water"},
    "caffeine": {"min": 0, "max": 10, "desc": "Cups of coffee/tea"},
    "alcohol": {"min": 0, "max": 10, "desc": "Drinks"},
    "pain": {"min": 0, "max": 10, "desc": "Pain level (0=none, 10=severe)"},
}


def show_metric_menu() -> None:
    """Display available common metrics."""
    table = Table(title="Common Metrics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Range", style="green")
    table.add_column("Description", style="white")
    
    for name, info in COMMON_METRICS.items():
        table.add_row(name, f"{info['min']}-{info['max']}", info["desc"])
    
    console.print(table)
    console.print("\n[dim]You can also enter any custom metric name.[/dim]\n")


def show_today_entries(db: Database) -> list:
    """Display today's logged entries."""
    entries = get_today_entries(db)
    
    if not entries:
        console.print("[dim]No entries logged today yet.[/dim]\n")
        return []
    
    table = Table(title=f"Today's Entries ({date.today().isoformat()})", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Note", style="white")
    table.add_column("Tags", style="yellow")
    
    for i, entry in enumerate(entries, 1):
        table.add_row(
            str(i),
            entry["metric"],
            str(entry["value"]),
            entry.get("note", "") or "",
            ", ".join(entry.get("tags", []) or []),
        )
    
    console.print(table)
    console.print()
    return entries


def prompt_metric_entry(db: Database) -> bool:
    """Prompt user for a single metric entry. Returns False to exit."""
    # Get metric name
    metric = Prompt.ask(
        "[cyan]Metric[/cyan] (or 'q' to quit, '?' for list)",
        default="mood"
    ).strip().lower()
    
    if metric == "q":
        return False
    
    if metric == "?":
        show_metric_menu()
        return True
    
    # Get value with range hint if known metric
    if metric in COMMON_METRICS:
        info = COMMON_METRICS[metric]
        prompt_text = f"[green]Value[/green] ({info['min']}-{info['max']})"
    else:
        prompt_text = "[green]Value[/green]"
    
    try:
        value = FloatPrompt.ask(prompt_text)
    except (ValueError, KeyboardInterrupt):
        console.print("[red]Invalid value. Skipping.[/red]")
        return True
    
    # Optional note
    note = Prompt.ask("[white]Note[/white] (optional)", default="").strip() or None
    
    # Optional tags
    tags_str = Prompt.ask("[yellow]Tags[/yellow] (comma-separated, optional)", default="").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
    
    # Log it
    log_metric(db, metric, value, note=note, tags=tags)
    console.print(f"[green]Logged {metric}={value}[/green]\n")
    
    return True


def prompt_delete_entry(db: Database, entries: list) -> None:
    """Prompt to delete an entry."""
    if not entries:
        console.print("[dim]No entries to delete.[/dim]")
        return
    
    entry_num = Prompt.ask(
        "[red]Entry # to delete[/red] (or 'c' to cancel)",
        default="c"
    ).strip()
    
    if entry_num.lower() == "c":
        return
    
    try:
        idx = int(entry_num) - 1
        if 0 <= idx < len(entries):
            entry = entries[idx]
            if Confirm.ask(f"Delete {entry['metric']}={entry['value']}?"):
                delete_entry(db, entry["id"])
                console.print("[green]Deleted.[/green]\n")
        else:
            console.print("[red]Invalid entry number.[/red]")
    except ValueError:
        console.print("[red]Invalid input.[/red]")


def interactive_log(db: Database) -> None:
    """Run interactive logging session."""
    console.print(Panel.fit(
        "[bold]Resonance - Quick Log[/bold]\n"
        "Log metrics interactively. Type 'q' to quit, '?' for metric list.",
        border_style="blue"
    ))
    console.print()
    
    # Show today's entries
    entries = show_today_entries(db)
    
    while True:
        action = Prompt.ask(
            "[bold]Action[/bold]",
            choices=["log", "view", "delete", "quit"],
            default="log"
        )
        
        if action == "quit":
            console.print("[dim]Goodbye![/dim]")
            break
        elif action == "view":
            entries = show_today_entries(db)
        elif action == "delete":
            entries = show_today_entries(db)
            prompt_delete_entry(db, entries)
        elif action == "log":
            if not prompt_metric_entry(db):
                console.print("[dim]Goodbye![/dim]")
                break


def quick_log(db: Database) -> None:
    """Quick logging mode - just log metrics until quit."""
    console.print("[bold blue]Quick Log Mode[/bold blue] - Enter metrics (q to quit)\n")
    
    while prompt_metric_entry(db):
        pass
