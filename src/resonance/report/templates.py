"""Natural language templates for describing analysis results."""

from ..analysis.correlation import CorrelationResult
from ..analysis.patterns import WeekdayPattern
from ..analysis.trends import TrendResult

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def describe_correlation(r: CorrelationResult) -> str:
    """Generate natural language description of a correlation.

    Args:
        r: Correlation result to describe

    Returns:
        Human-readable description
    """
    direction = "higher" if r.correlation > 0 else "lower"
    strength = "strongly" if abs(r.correlation) > 0.5 else "moderately"

    if r.lag_days == 0:
        return (
            f"{r.metric1} {strength} correlates with {r.metric2} "
            f"(r={r.correlation:.2f}). "
            f"When {r.metric1} is higher, {r.metric2} tends to be {direction}."
        )
    else:
        return (
            f"{r.metric1} today predicts {r.metric2} {r.lag_days} day(s) later "
            f"(r={r.correlation:.2f}). "
            f"Higher {r.metric1} is followed by {direction} {r.metric2}."
        )


def describe_weekday_pattern(p: WeekdayPattern) -> str:
    """Generate natural language description of a weekday pattern.

    Args:
        p: Weekday pattern to describe

    Returns:
        Human-readable description
    """
    day_name = WEEKDAY_NAMES[p.weekday] if 0 <= p.weekday <= 6 else f"Day {p.weekday}"
    direction = "higher" if p.difference_pct > 0 else "lower"
    pct = abs(round(p.difference_pct))
    return f"{day_name}s show {pct}% {direction} {p.metric} than average."


def describe_trend(t: TrendResult) -> str:
    """Generate natural language description of a trend.

    Args:
        t: Trend result to describe

    Returns:
        Human-readable description
    """
    if t.direction == "stable":
        return f"Your {t.metric} has been stable."

    verb = "increased" if t.direction == "up" else "decreased"
    pct = abs(round(t.change_pct))
    return f"Your {t.metric} {verb} by {pct}% this period."


def describe_data_quality(quality: dict[str, tuple[int, int]]) -> str:
    """Generate description of data quality.

    Args:
        quality: Dict mapping metric names to (days_with_data, total_days)

    Returns:
        Human-readable description
    """
    if not quality:
        return "No data quality information available."

    lines = ["Data coverage:"]
    for metric, (days, total) in quality.items():
        if total > 0:
            pct = round((days / total) * 100)
            lines.append(f"  {metric}: {days}/{total} days ({pct}%)")
        else:
            lines.append(f"  {metric}: no data")

    return "\n".join(lines)


def generate_insight_summary(
    patterns: list[CorrelationResult],
    weekday_effects: list[WeekdayPattern],
    trends: list[TrendResult],
) -> str:
    """Generate a summary of key insights.

    Args:
        patterns: List of correlation results
        weekday_effects: List of weekday patterns
        trends: List of trend results

    Returns:
        Summary paragraph
    """
    insights = []

    # Top correlation
    if patterns:
        top = patterns[0]
        insights.append(describe_correlation(top))

    # Strongest weekday effect
    if weekday_effects:
        strongest = max(weekday_effects, key=lambda x: abs(x.difference_pct))
        insights.append(describe_weekday_pattern(strongest))

    # Notable trends
    notable_trends = [t for t in trends if t.direction != "stable"]
    if notable_trends:
        for t in notable_trends[:2]:
            insights.append(describe_trend(t))

    if not insights:
        return "No significant patterns found in your data yet. Keep logging!"

    return " ".join(insights)
