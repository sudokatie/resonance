"""Sleep quality scoring and analysis.

Provides a composite sleep quality score based on:
- Duration (how long you slept)
- Efficiency (percentage of time in bed actually sleeping)
- Stages (balance of deep, REM, and light sleep)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database


# Ideal sleep targets (based on sleep science recommendations)
IDEAL_DURATION_HOURS = 7.5  # 7-8 hours is recommended
MIN_DURATION_HOURS = 6.0
MAX_DURATION_HOURS = 9.0

IDEAL_EFFICIENCY = 85.0  # 85%+ is considered good
MIN_EFFICIENCY = 70.0

# Sleep stage targets (percentage of total sleep)
IDEAL_DEEP_PERCENT = 20.0  # 15-25% is ideal
IDEAL_REM_PERCENT = 25.0   # 20-25% is ideal

# Score weights
DURATION_WEIGHT = 0.35
EFFICIENCY_WEIGHT = 0.30
STAGES_WEIGHT = 0.35


@dataclass
class SleepStages:
    """Sleep stage breakdown."""
    deep_hours: float
    rem_hours: float
    light_hours: float
    
    @property
    def total_hours(self) -> float:
        """Total hours across all stages."""
        return self.deep_hours + self.rem_hours + self.light_hours
    
    @property
    def deep_percent(self) -> float:
        """Percentage of sleep in deep stage."""
        if self.total_hours == 0:
            return 0.0
        return (self.deep_hours / self.total_hours) * 100
    
    @property
    def rem_percent(self) -> float:
        """Percentage of sleep in REM stage."""
        if self.total_hours == 0:
            return 0.0
        return (self.rem_hours / self.total_hours) * 100
    
    @property
    def light_percent(self) -> float:
        """Percentage of sleep in light stage."""
        if self.total_hours == 0:
            return 0.0
        return (self.light_hours / self.total_hours) * 100


@dataclass
class SleepScore:
    """Composite sleep quality score."""
    date: str
    total_score: float  # 0-100
    duration_score: float  # 0-100
    efficiency_score: float  # 0-100
    stages_score: float  # 0-100
    duration_hours: float
    efficiency: float
    stages: Optional[SleepStages] = None
    
    @property
    def rating(self) -> str:
        """Get a text rating based on score."""
        if self.total_score >= 85:
            return "Excellent"
        elif self.total_score >= 70:
            return "Good"
        elif self.total_score >= 55:
            return "Fair"
        else:
            return "Poor"


def score_duration(hours: float) -> float:
    """Score sleep duration on a 0-100 scale.
    
    Optimal is around 7.5 hours. Too little or too much is penalized.
    
    Args:
        hours: Hours of sleep
        
    Returns:
        Score from 0-100
    """
    if hours < MIN_DURATION_HOURS:
        # Linear penalty below minimum
        return max(0, (hours / MIN_DURATION_HOURS) * 70)
    elif hours <= IDEAL_DURATION_HOURS:
        # Scale up to 100 as we approach ideal
        return 70 + ((hours - MIN_DURATION_HOURS) / (IDEAL_DURATION_HOURS - MIN_DURATION_HOURS)) * 30
    elif hours <= MAX_DURATION_HOURS:
        # Perfect score in the ideal range
        return 100.0
    else:
        # Slight penalty for oversleeping
        excess = hours - MAX_DURATION_HOURS
        return max(60, 100 - (excess * 10))


def score_efficiency(efficiency: float) -> float:
    """Score sleep efficiency on a 0-100 scale.
    
    Args:
        efficiency: Sleep efficiency percentage (0-100)
        
    Returns:
        Score from 0-100
    """
    if efficiency >= IDEAL_EFFICIENCY:
        return 100.0
    elif efficiency >= MIN_EFFICIENCY:
        # Linear scale from min to ideal
        return ((efficiency - MIN_EFFICIENCY) / (IDEAL_EFFICIENCY - MIN_EFFICIENCY)) * 100
    else:
        # Below minimum - scale down further
        return max(0, (efficiency / MIN_EFFICIENCY) * 70)


def score_stages(stages: SleepStages) -> float:
    """Score sleep stages balance on a 0-100 scale.
    
    Args:
        stages: Sleep stage breakdown
        
    Returns:
        Score from 0-100
    """
    if stages.total_hours == 0:
        return 0.0
    
    # Score deep sleep (target ~20%)
    deep_diff = abs(stages.deep_percent - IDEAL_DEEP_PERCENT)
    deep_score = max(0, 100 - (deep_diff * 4))  # 4 points per % deviation
    
    # Score REM sleep (target ~25%)
    rem_diff = abs(stages.rem_percent - IDEAL_REM_PERCENT)
    rem_score = max(0, 100 - (rem_diff * 4))
    
    # Weight: deep is slightly more important for recovery
    return (deep_score * 0.55) + (rem_score * 0.45)


def calculate_sleep_score(
    duration_hours: float,
    efficiency: float,
    stages: Optional[SleepStages] = None,
    date: str = "",
) -> SleepScore:
    """Calculate composite sleep quality score.
    
    Args:
        duration_hours: Total hours of sleep
        efficiency: Sleep efficiency percentage
        stages: Optional sleep stage breakdown
        date: Date string (YYYY-MM-DD)
        
    Returns:
        SleepScore with component scores
    """
    duration_score = score_duration(duration_hours)
    efficiency_score = score_efficiency(efficiency)
    
    if stages:
        stages_score = score_stages(stages)
        total = (
            duration_score * DURATION_WEIGHT +
            efficiency_score * EFFICIENCY_WEIGHT +
            stages_score * STAGES_WEIGHT
        )
    else:
        # Without stage data, split weight between duration and efficiency
        stages_score = 0.0
        total = (
            duration_score * 0.55 +
            efficiency_score * 0.45
        )
    
    return SleepScore(
        date=date,
        total_score=total,
        duration_score=duration_score,
        efficiency_score=efficiency_score,
        stages_score=stages_score,
        duration_hours=duration_hours,
        efficiency=efficiency,
        stages=stages,
    )


def get_sleep_score_for_date(db: Database, date: str) -> Optional[SleepScore]:
    """Get sleep score for a specific date.
    
    Args:
        db: Database instance
        date: Date string (YYYY-MM-DD)
        
    Returns:
        SleepScore or None if no sleep data
    """
    metrics = db.get_metrics_for_date(date)
    
    # Extract sleep metrics
    duration = None
    efficiency = None
    deep_hours = None
    rem_hours = None
    light_hours = None
    
    for m in metrics:
        if m.metric_name == "sleep_hours":
            duration = m.value
        elif m.metric_name == "sleep_efficiency":
            efficiency = m.value
        elif m.metric_name == "deep_sleep_hours":
            deep_hours = m.value
        elif m.metric_name == "rem_sleep_hours":
            rem_hours = m.value
        elif m.metric_name == "light_sleep_hours":
            light_hours = m.value
    
    if duration is None:
        return None
    
    # Build stages if we have the data
    stages = None
    if deep_hours is not None and rem_hours is not None and light_hours is not None:
        stages = SleepStages(
            deep_hours=deep_hours,
            rem_hours=rem_hours,
            light_hours=light_hours,
        )
    
    # Default efficiency if not available
    if efficiency is None:
        efficiency = 85.0  # Assume average
    
    return calculate_sleep_score(
        duration_hours=duration,
        efficiency=efficiency,
        stages=stages,
        date=date,
    )


def get_sleep_scores_for_range(
    db: Database,
    start_date: str,
    end_date: str,
) -> list[SleepScore]:
    """Get sleep scores for a date range.
    
    Args:
        db: Database instance
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        List of SleepScore objects, one per day with data
    """
    scores = []
    
    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        score = get_sleep_score_for_date(db, date_str)
        if score:
            scores.append(score)
        current += timedelta(days=1)
    
    return scores


def get_sleep_trend(scores: list[SleepScore]) -> dict:
    """Analyze sleep score trend.
    
    Args:
        scores: List of SleepScore objects (should be chronological)
        
    Returns:
        Dictionary with trend analysis
    """
    if len(scores) < 2:
        return {
            "direction": "insufficient_data",
            "change": 0.0,
            "average": scores[0].total_score if scores else 0.0,
        }
    
    # Calculate average
    avg = sum(s.total_score for s in scores) / len(scores)
    
    # Compare first half to second half
    mid = len(scores) // 2
    first_half_avg = sum(s.total_score for s in scores[:mid]) / mid if mid > 0 else avg
    second_half_avg = sum(s.total_score for s in scores[mid:]) / (len(scores) - mid)
    
    change = second_half_avg - first_half_avg
    
    if change > 5:
        direction = "improving"
    elif change < -5:
        direction = "declining"
    else:
        direction = "stable"
    
    return {
        "direction": direction,
        "change": round(change, 1),
        "average": round(avg, 1),
        "best_score": max(s.total_score for s in scores),
        "worst_score": min(s.total_score for s in scores),
    }


def format_sleep_report(score: SleepScore) -> str:
    """Format a sleep score as a text report.
    
    Args:
        score: SleepScore to format
        
    Returns:
        Formatted string
    """
    lines = [
        f"Sleep Quality Report for {score.date}",
        "=" * 40,
        f"",
        f"Overall Score: {score.total_score:.0f}/100 ({score.rating})",
        f"",
        f"Components:",
        f"  Duration:   {score.duration_score:.0f}/100 ({score.duration_hours:.1f} hours)",
        f"  Efficiency: {score.efficiency_score:.0f}/100 ({score.efficiency:.0f}%)",
    ]
    
    if score.stages:
        lines.append(f"  Stages:     {score.stages_score:.0f}/100")
        lines.append(f"    - Deep:  {score.stages.deep_hours:.1f}h ({score.stages.deep_percent:.0f}%)")
        lines.append(f"    - REM:   {score.stages.rem_hours:.1f}h ({score.stages.rem_percent:.0f}%)")
        lines.append(f"    - Light: {score.stages.light_hours:.1f}h ({score.stages.light_percent:.0f}%)")
    
    return "\n".join(lines)
