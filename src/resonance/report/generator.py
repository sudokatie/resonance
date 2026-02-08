"""Report generation from analysis results."""

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..database import Database
from ..analysis.correlation import CorrelationResult, find_all_correlations
from ..analysis.patterns import WeekdayPattern, find_weekday_patterns
from ..analysis.trends import TrendResult, week_over_week, month_over_month


@dataclass
class Report:
    """A complete analysis report."""

    date_range: tuple[str, str]
    patterns: list[CorrelationResult] = field(default_factory=list)
    weekday_effects: list[WeekdayPattern] = field(default_factory=list)
    trends: list[TrendResult] = field(default_factory=list)
    data_quality: dict[str, tuple[int, int]] = field(default_factory=dict)


def generate_report(
    db: Database,
    period: str = "week",
    reference_date: Optional[date] = None,
) -> Report:
    """Generate a report from database data.

    Args:
        db: Database instance
        period: 'week' or 'month'
        reference_date: Date to use as "today" (defaults to actual today)

    Returns:
        Report with patterns, weekday effects, trends, and data quality
    """
    today = reference_date or date.today()

    # Calculate date range
    if period == "week":
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
    else:  # month
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()

    # Get data
    df = db.get_metrics_df()
    if df.empty:
        return Report(date_range=(start, end))

    # Find patterns
    patterns = find_all_correlations(df)

    # Find weekday effects
    weekday_effects = find_weekday_patterns(df)

    # Find trends
    trends = []
    for metric in df.columns:
        if metric == "date":
            continue
        if period == "week":
            trend = week_over_week(df, metric, reference_date=today)
        else:
            trend = month_over_month(df, metric, reference_date=today)
        if trend:
            trends.append(trend)

    # Calculate data quality
    data_quality = {}
    for metric in df.columns:
        if metric == "date":
            continue
        days_with_data = int(df[metric].notna().sum())
        total_days = len(df)
        data_quality[metric] = (days_with_data, total_days)

    return Report(
        date_range=(start, end),
        patterns=patterns,
        weekday_effects=weekday_effects,
        trends=trends,
        data_quality=data_quality,
    )


def generate_report_from_df(
    df: pd.DataFrame,
    period: str = "week",
    reference_date: Optional[date] = None,
) -> Report:
    """Generate a report directly from a DataFrame.

    Args:
        df: DataFrame with metrics as columns, date index
        period: 'week' or 'month'
        reference_date: Date to use as "today" (defaults to actual today)

    Returns:
        Report with patterns, weekday effects, trends, and data quality
    """
    today = reference_date or date.today()

    # Calculate date range
    if period == "week":
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
    else:  # month
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()

    if df.empty:
        return Report(date_range=(start, end))

    # Find patterns
    patterns = find_all_correlations(df)

    # Find weekday effects
    weekday_effects = find_weekday_patterns(df)

    # Find trends
    trends = []
    for metric in df.columns:
        if metric == "date":
            continue
        if period == "week":
            trend = week_over_week(df, metric, reference_date=today)
        else:
            trend = month_over_month(df, metric, reference_date=today)
        if trend:
            trends.append(trend)

    # Calculate data quality
    data_quality = {}
    for metric in df.columns:
        if metric == "date":
            continue
        days_with_data = int(df[metric].notna().sum())
        total_days = len(df)
        data_quality[metric] = (days_with_data, total_days)

    return Report(
        date_range=(start, end),
        patterns=patterns,
        weekday_effects=weekday_effects,
        trends=trends,
        data_quality=data_quality,
    )


def format_json(report: Report) -> str:
    """Format report as JSON.

    Args:
        report: Report to format

    Returns:
        JSON string
    """

    def serialize(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    return json.dumps(asdict(report), default=serialize, indent=2)


def format_text(report: Report) -> str:
    """Format report as plain text.

    Args:
        report: Report to format

    Returns:
        Plain text string
    """
    lines = []
    lines.append(f"Resonance Report: {report.date_range[0]} to {report.date_range[1]}")
    lines.append("=" * 60)

    # Patterns
    if report.patterns:
        lines.append("\nCorrelations Found:")
        for p in report.patterns[:5]:  # Top 5
            direction = "+" if p.correlation > 0 else "-"
            lines.append(
                f"  {p.metric1} <-> {p.metric2}: {direction}{abs(p.correlation):.2f} "
                f"(lag={p.lag_days}d, {p.confidence} confidence)"
            )
    else:
        lines.append("\nNo significant correlations found.")

    # Weekday effects
    if report.weekday_effects:
        lines.append("\nWeekday Patterns:")
        for w in report.weekday_effects[:5]:
            direction = "higher" if w.difference_pct > 0 else "lower"
            lines.append(
                f"  {w.weekday_name}: {w.metric} is {abs(w.difference_pct):.0f}% {direction}"
            )
    else:
        lines.append("\nNo significant weekday patterns found.")

    # Trends
    if report.trends:
        lines.append("\nTrends:")
        for t in report.trends:
            if t.direction == "stable":
                lines.append(f"  {t.metric}: stable")
            else:
                arrow = "↑" if t.direction == "up" else "↓"
                lines.append(f"  {t.metric}: {arrow} {abs(t.change_pct):.0f}%")
    else:
        lines.append("\nNo trend data available.")

    # Data quality
    if report.data_quality:
        lines.append("\nData Quality:")
        for metric, (days, total) in report.data_quality.items():
            pct = (days / total) * 100 if total > 0 else 0
            lines.append(f"  {metric}: {days}/{total} days ({pct:.0f}%)")

    return "\n".join(lines)


def format_markdown(report: Report) -> str:
    """Format report as Markdown.

    Args:
        report: Report to format

    Returns:
        Markdown string
    """
    lines = []
    lines.append("# Resonance Report")
    lines.append(f"**Period:** {report.date_range[0]} to {report.date_range[1]}")
    lines.append("")

    # Patterns
    lines.append("## Correlations")
    if report.patterns:
        lines.append("| Metrics | Correlation | Lag | Confidence |")
        lines.append("|---------|-------------|-----|------------|")
        for p in report.patterns[:5]:
            lines.append(
                f"| {p.metric1} ↔ {p.metric2} | {p.correlation:.2f} | {p.lag_days}d | {p.confidence} |"
            )
    else:
        lines.append("No significant correlations found.")
    lines.append("")

    # Weekday effects
    lines.append("## Weekday Patterns")
    if report.weekday_effects:
        for w in report.weekday_effects[:5]:
            direction = "higher" if w.difference_pct > 0 else "lower"
            lines.append(
                f"- **{w.weekday_name}**: {w.metric} is {abs(w.difference_pct):.0f}% {direction}"
            )
    else:
        lines.append("No significant weekday patterns found.")
    lines.append("")

    # Trends
    lines.append("## Trends")
    if report.trends:
        for t in report.trends:
            if t.direction == "stable":
                lines.append(f"- **{t.metric}**: stable")
            else:
                emoji = "📈" if t.direction == "up" else "📉"
                lines.append(f"- **{t.metric}**: {emoji} {abs(t.change_pct):.0f}%")
    else:
        lines.append("No trend data available.")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    if report.data_quality:
        lines.append("| Metric | Coverage |")
        lines.append("|--------|----------|")
        for metric, (days, total) in report.data_quality.items():
            pct = (days / total) * 100 if total > 0 else 0
            lines.append(f"| {metric} | {days}/{total} ({pct:.0f}%) |")

    return "\n".join(lines)
