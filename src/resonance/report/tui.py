"""TUI dashboard for viewing reports in terminal."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.live import Live
from rich.layout import Layout

from .generator import Report


def _sparkline_ascii(values: list[float], width: int = 20) -> str:
    """Generate ASCII sparkline from values."""
    if not values or len(values) < 2:
        return "-" * width
    
    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val
    
    if val_range == 0:
        return chars[3] * min(len(values), width)
    
    # Sample values if too many
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
    
    result = ""
    for v in sampled:
        idx = int((v - min_val) / val_range * 7)
        idx = min(7, max(0, idx))
        result += chars[idx]
    
    return result


def _correlation_color(corr: float) -> str:
    """Get color for correlation value."""
    if corr > 0.7:
        return "green"
    elif corr > 0.4:
        return "yellow"
    elif corr < -0.7:
        return "red"
    elif corr < -0.4:
        return "magenta"
    return "white"


def _confidence_badge(confidence: str) -> Text:
    """Create colored confidence badge."""
    colors = {"high": "green", "medium": "yellow", "low": "red"}
    return Text(f"[{confidence}]", style=colors.get(confidence, "white"))


def render_patterns_panel(report: Report) -> Panel:
    """Render correlations as a panel."""
    if not report.patterns:
        return Panel("[dim]No patterns found[/dim]", title="Patterns")
    
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Metrics", style="cyan")
    table.add_column("Correlation", justify="right")
    table.add_column("Confidence", justify="center")
    table.add_column("Lag", justify="right")
    
    # Sort by absolute correlation
    sorted_patterns = sorted(report.patterns, key=lambda p: abs(p.correlation), reverse=True)
    
    for pattern in sorted_patterns[:10]:  # Top 10
        corr = pattern.correlation
        color = _correlation_color(corr)
        corr_str = f"[{color}]{corr:+.2f}[/{color}]"
        
        metrics = f"{pattern.metric1} ↔ {pattern.metric2}"
        lag = f"{pattern.lag_days}d" if pattern.lag_days else "-"
        
        table.add_row(metrics, corr_str, pattern.confidence, lag)
    
    return Panel(table, title="[bold]Patterns[/bold]", border_style="blue")


def render_weekday_panel(report: Report) -> Panel:
    """Render weekday effects as a panel."""
    if not report.weekday_effects:
        return Panel("[dim]No weekday effects found[/dim]", title="Weekday Effects")
    
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Metric", style="cyan")
    table.add_column("Day", justify="center")
    table.add_column("Diff", justify="right")
    table.add_column("Significant", justify="center")
    
    # Show significant weekday effects
    significant = [e for e in report.weekday_effects if e.significant]
    
    for effect in significant[:8]:
        diff_pct = effect.difference_pct
        if diff_pct > 0:
            diff_str = f"[green]+{diff_pct:.1%}[/green]"
        else:
            diff_str = f"[red]{diff_pct:.1%}[/red]"
        
        sig_str = "[green]Yes[/green]" if effect.significant else "[dim]No[/dim]"
        
        table.add_row(
            effect.metric,
            effect.weekday_name,
            diff_str,
            sig_str
        )
    
    return Panel(table, title="[bold]Weekday Effects[/bold]", border_style="green")


def render_trends_panel(report: Report) -> Panel:
    """Render trends as a panel."""
    if not report.trends:
        return Panel("[dim]No trend data available[/dim]", title="Trends")
    
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Metric", style="cyan")
    table.add_column("Change", justify="right")
    table.add_column("Direction", justify="center")
    
    for trend in report.trends[:8]:
        # Change color based on direction
        if trend.direction == "up":
            change_str = f"[green]+{trend.change_pct:.1%}[/green]"
            arrow = "[green]↑[/green]"
        elif trend.direction == "down":
            change_str = f"[red]{trend.change_pct:.1%}[/red]"
            arrow = "[red]↓[/red]"
        else:
            change_str = "[dim]0%[/dim]"
            arrow = "[dim]→[/dim]"
        
        table.add_row(trend.metric, change_str, arrow)
    
    return Panel(table, title="[bold]Trends[/bold]", border_style="yellow")


def render_quality_panel(report: Report) -> Panel:
    """Render data quality metrics."""
    if not report.data_quality:
        return Panel("[dim]No data quality info[/dim]", title="Data Quality")
    
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Metric", style="cyan")
    table.add_column("Completeness", justify="right")
    table.add_column("Coverage", justify="left")
    
    for metric, (available, total) in report.data_quality.items():
        pct = available / total if total > 0 else 0
        
        # Color based on completeness
        if pct >= 0.9:
            color = "green"
        elif pct >= 0.7:
            color = "yellow"
        else:
            color = "red"
        
        # Progress bar
        bar_width = 10
        filled = int(pct * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        table.add_row(
            metric,
            f"[{color}]{pct:.0%}[/{color}]",
            f"[{color}]{bar}[/{color}]"
        )
    
    return Panel(table, title="[bold]Data Quality[/bold]", border_style="magenta")


def render_dashboard(report: Report, console: Optional[Console] = None) -> None:
    """Render full TUI dashboard.
    
    Args:
        report: Report to display
        console: Optional console instance (creates new if not provided)
    """
    if console is None:
        console = Console()
    
    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Resonance Dashboard[/bold]\n"
            f"[dim]Period: {report.date_range[0]} to {report.date_range[1]}[/dim]",
            style="bold blue"
        )
    )
    console.print()
    
    # Patterns and Weekday side by side
    patterns = render_patterns_panel(report)
    weekday = render_weekday_panel(report)
    console.print(Columns([patterns, weekday], equal=True, expand=True))
    console.print()
    
    # Trends and Quality side by side
    trends = render_trends_panel(report)
    quality = render_quality_panel(report)
    console.print(Columns([trends, quality], equal=True, expand=True))
    console.print()


def render_correlation_heatmap(report: Report, console: Optional[Console] = None) -> None:
    """Render correlation matrix as ASCII heatmap.
    
    Args:
        report: Report containing patterns
        console: Optional console instance
    """
    if console is None:
        console = Console()
    
    if not report.patterns:
        console.print("[dim]No correlations to display[/dim]")
        return
    
    # Extract unique metrics
    metrics = set()
    for p in report.patterns:
        metrics.add(p.metric1)
        metrics.add(p.metric2)
    metrics = sorted(metrics)
    
    if len(metrics) > 10:
        metrics = metrics[:10]  # Limit size
    
    # Build correlation matrix
    matrix: dict[tuple[str, str], float] = {}
    for p in report.patterns:
        matrix[(p.metric1, p.metric2)] = p.correlation
        matrix[(p.metric2, p.metric1)] = p.correlation
    
    # Header row
    header = "".ljust(15) + " ".join(m[:6].ljust(6) for m in metrics)
    console.print(f"[bold]{header}[/bold]")
    
    # Heatmap characters
    chars = "░▒▓█"
    
    for m1 in metrics:
        row = m1[:15].ljust(15)
        for m2 in metrics:
            if m1 == m2:
                row += "[white]  ●   [/white]"
            elif (m1, m2) in matrix:
                corr = matrix[(m1, m2)]
                color = _correlation_color(corr)
                # Use block characters for intensity
                intensity = int(abs(corr) * 3)
                char = chars[min(intensity, 3)]
                sign = "+" if corr > 0 else "-"
                row += f"[{color}] {sign}{char * 4} [/{color}]"
            else:
                row += "[dim]  ·   [/dim]"
        console.print(row)
    
    # Legend
    console.print()
    console.print("[dim]Legend: [green]+[/green] positive [red]-[/red] negative | ░ weak ▒ moderate ▓ strong █ very strong[/dim]")
