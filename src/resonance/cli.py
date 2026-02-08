"""CLI entry point for Resonance."""

from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .database import Database
from .ingest.health import import_health
from .ingest.manual import log_metric, parse_tags
from .analysis.correlation import find_all_correlations
from .models import PatternRecord
from .report.generator import generate_report, format_text, format_json, format_markdown

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


def get_db() -> Database:
    """Get database instance from config."""
    config = load_config()
    return Database(config.db_path)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Resonance - Find patterns in your life."""
    pass


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Data source (health)"),
    path: str = typer.Argument(..., help="Path to data file"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-V", help="Verbose output"),
) -> None:
    """Import data from a source."""
    db = get_db()
    file_path = Path(path)

    if not file_path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)

    if source == "health":
        count = import_health(db, file_path, dry_run=dry_run, verbose=verbose, console=console if verbose else None)
        if count == 0:
            console.print("[yellow]No supported health data found in export[/yellow]")
            raise typer.Exit(0)
        if dry_run:
            console.print(f"[yellow]Would import {count} daily metrics[/yellow]")
        else:
            console.print(f"[green]Imported {count} daily metrics from Apple Health[/green]")
    else:
        console.print(f"[red]Unknown source: {source}[/red]")
        console.print("Supported sources: health")
        raise typer.Exit(1)


@app.command()
def log(
    metric: str = typer.Argument(..., help="Metric name (e.g., mood, energy)"),
    value: float = typer.Argument(..., help="Metric value"),
    note: Optional[str] = typer.Option(None, "--note", "-n", help="Optional note"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
) -> None:
    """Log a manual metric value for today."""
    db = get_db()
    tag_list = parse_tags(tags) if tags else None

    log_metric(db, metric, value, note=note, tags=tag_list)
    today = date.today().isoformat()
    console.print(f"[green]Logged {metric}={value} for {today}[/green]")


@app.command()
def analyze(
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    metrics: Optional[str] = typer.Option(
        None, "--metrics", help="Comma-separated metrics to analyze"
    ),
    min_days: int = typer.Option(14, "--min-days", help="Minimum days of data required"),
    p_threshold: float = typer.Option(0.05, "--p-threshold", help="P-value threshold"),
    min_correlation: float = typer.Option(0.3, "--min-correlation", help="Minimum correlation strength"),
    lag: int = typer.Option(1, "--lag", help="Maximum lag days for correlation"),
    save: bool = typer.Option(False, "--save", help="Save patterns to database"),
) -> None:
    """Run correlation analysis."""
    db = get_db()
    df = db.get_metrics_df(from_date, to_date)

    if df.empty:
        console.print("[yellow]No data found for the specified range.[/yellow]")
        raise typer.Exit(0)

    # Filter metrics if specified
    if metrics:
        metric_list = [m.strip() for m in metrics.split(",")]
        df = df[[c for c in df.columns if c in metric_list]]

    # Find correlations
    patterns = find_all_correlations(df, max_lag=lag, min_correlation=min_correlation, p_threshold=p_threshold, min_days=min_days)

    if not patterns:
        console.print("[yellow]No significant correlations found.[/yellow]")
        raise typer.Exit(0)

    # Display results
    table = Table(title="Correlations")
    table.add_column("Metric 1")
    table.add_column("Metric 2")
    table.add_column("Correlation")
    table.add_column("Lag")
    table.add_column("Confidence")

    for p in patterns[:10]:  # Top 10
        table.add_row(
            p.metric1,
            p.metric2,
            f"{p.correlation:+.2f}",
            f"{p.lag_days}d",
            p.confidence,
        )

    console.print(table)
    console.print(f"\nFound {len(patterns)} correlations total.")

    # Save if requested
    if save:
        for p in patterns:
            pattern = PatternRecord(
                metric1=p.metric1,
                metric2=p.metric2,
                correlation=p.correlation,
                p_value=p.p_value,
                lag_days=p.lag_days,
                sample_size=p.sample_size,
                confidence=p.confidence,
            )
            db.insert_pattern(pattern)
        console.print(f"[green]Saved {len(patterns)} patterns to database.[/green]")


@app.command()
def report(
    period: str = typer.Option("week", "--period", "-p", help="Report period (week, month, quarter, year)"),
    fmt: str = typer.Option("text", "--format", "-f", help="Output format (text, json, markdown)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate pattern report."""
    db = get_db()
    rpt = generate_report(db, period=period)

    if fmt == "json":
        result = format_json(rpt)
    elif fmt == "markdown":
        result = format_markdown(rpt)
    else:
        result = format_text(rpt)

    if output:
        Path(output).write_text(result)
        console.print(f"[green]Report saved to {output}[/green]")
    else:
        console.print(result)


@app.command()
def status() -> None:
    """Show data overview."""
    config = load_config()
    db = Database(config.db_path)

    # Display status header
    console.print("[bold]Resonance Data Status[/bold]")
    console.print("=" * 40)

    # Database info
    db_path = config.db_path
    if db_path.exists():
        db_size_bytes = db_path.stat().st_size
        db_size_mb = db_size_bytes / (1024 * 1024)
        console.print(f"Database: {db_path} ({db_size_mb:.1f} MB)")
    else:
        console.print(f"Database: {db_path} (not created)")

    # Get metrics
    metrics = db.get_metric_names()
    if not metrics:
        console.print("\n[yellow]No data yet. Use 'resonance ingest' or 'resonance log' to add data.[/yellow]")
        raise typer.Exit(0)

    # Metrics table
    console.print("\nMetrics:")
    for metric in metrics:
        count = db.get_metric_count(metric)
        metric_range = db.get_date_range(metric)
        if metric_range:
            console.print(f"  {metric}: {count} days ({metric_range[0]} - {metric_range[1]})")
        else:
            console.print(f"  {metric}: {count} days")

    # Pattern count and last analysis
    patterns = db.get_patterns()
    last_analysis = db.get_last_analysis_date()
    console.print(f"\nRecent Patterns Found: {len(patterns)}")
    if last_analysis:
        console.print(f"Last Analysis: {last_analysis}")


if __name__ == "__main__":
    app()
