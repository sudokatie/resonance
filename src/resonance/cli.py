"""CLI entry point for Resonance."""

import typer
from rich.console import Console

from . import __version__

app = typer.Typer(
    name="resonance",
    help="Find patterns in your life.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"resonance {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit."
    ),
) -> None:
    """Resonance - Find patterns in your life."""
    pass


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Data source (health)"),
    path: str = typer.Argument(..., help="Path to data file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Import data from a source."""
    console.print(f"[yellow]ingest not yet implemented[/yellow]")


@app.command()
def log(
    metric: str = typer.Argument(..., help="Metric name (e.g., mood, energy)"),
    value: float = typer.Argument(..., help="Metric value"),
    note: str = typer.Option(None, "--note", "-n", help="Optional note"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
) -> None:
    """Log a manual metric value."""
    console.print(f"[yellow]log not yet implemented[/yellow]")


@app.command()
def analyze(
    from_date: str = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    metrics: str = typer.Option(None, "--metrics", help="Comma-separated metrics to analyze"),
    min_days: int = typer.Option(14, "--min-days", help="Minimum days of data required"),
    lag: int = typer.Option(1, "--lag", help="Maximum lag days for correlation"),
) -> None:
    """Run correlation analysis."""
    console.print(f"[yellow]analyze not yet implemented[/yellow]")


@app.command()
def report(
    period: str = typer.Option("week", "--period", "-p", help="Report period (week, month)"),
    format: str = typer.Option("text", "--format", "-f", help="Output format (text, json, markdown)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate pattern report."""
    console.print(f"[yellow]report not yet implemented[/yellow]")


@app.command()
def status() -> None:
    """Show data overview."""
    console.print(f"[yellow]status not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
