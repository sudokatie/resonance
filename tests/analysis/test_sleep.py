"""Tests for sleep quality scoring."""

import pytest
from resonance.analysis.sleep import (
    SleepStages,
    SleepScore,
    score_duration,
    score_efficiency,
    score_stages,
    calculate_sleep_score,
    get_sleep_trend,
    format_sleep_report,
)


class TestScoreDuration:
    """Tests for duration scoring."""
    
    def test_ideal_duration(self):
        """7.5 hours should score 100."""
        assert score_duration(7.5) == 100.0
    
    def test_optimal_range(self):
        """8-9 hours should score 100."""
        assert score_duration(8.0) == 100.0
        assert score_duration(9.0) == 100.0
    
    def test_below_minimum(self):
        """Less than 6 hours should be penalized."""
        score = score_duration(4.0)
        assert score < 70
        assert score > 0
    
    def test_above_maximum(self):
        """More than 9 hours should be slightly penalized."""
        score = score_duration(10.0)
        assert score < 100
        assert score >= 60
    
    def test_zero_duration(self):
        """Zero hours should score 0."""
        assert score_duration(0) == 0


class TestScoreEfficiency:
    """Tests for efficiency scoring."""
    
    def test_ideal_efficiency(self):
        """85%+ should score 100."""
        assert score_efficiency(85) == 100.0
        assert score_efficiency(95) == 100.0
    
    def test_minimum_efficiency(self):
        """70% is the low end of acceptable."""
        score = score_efficiency(70)
        assert score == 0.0  # At minimum threshold
    
    def test_below_minimum(self):
        """Below 70% is problematic."""
        score = score_efficiency(50)
        assert score < 70
    
    def test_midrange_efficiency(self):
        """77.5% should be about 50%."""
        score = score_efficiency(77.5)
        assert 40 <= score <= 60


class TestScoreStages:
    """Tests for sleep stages scoring."""
    
    def test_ideal_stages(self):
        """Ideal stage balance should score high."""
        # 20% deep, 25% REM, 55% light for 8 hours
        stages = SleepStages(
            deep_hours=1.6,   # 20%
            rem_hours=2.0,    # 25%
            light_hours=4.4,  # 55%
        )
        score = score_stages(stages)
        assert score >= 90
    
    def test_no_deep_sleep(self):
        """No deep sleep should penalize."""
        stages = SleepStages(
            deep_hours=0,
            rem_hours=2.0,
            light_hours=6.0,
        )
        score = score_stages(stages)
        assert score < 60
    
    def test_zero_total(self):
        """Zero total hours should return 0."""
        stages = SleepStages(deep_hours=0, rem_hours=0, light_hours=0)
        assert score_stages(stages) == 0


class TestSleepStages:
    """Tests for SleepStages dataclass."""
    
    def test_total_hours(self):
        """Total hours should sum all stages."""
        stages = SleepStages(deep_hours=1.5, rem_hours=2.0, light_hours=4.5)
        assert stages.total_hours == 8.0
    
    def test_percentages(self):
        """Percentages should be calculated correctly."""
        stages = SleepStages(deep_hours=2.0, rem_hours=2.0, light_hours=4.0)
        assert stages.deep_percent == 25.0
        assert stages.rem_percent == 25.0
        assert stages.light_percent == 50.0


class TestCalculateSleepScore:
    """Tests for composite sleep score calculation."""
    
    def test_excellent_sleep(self):
        """Excellent sleep should score high."""
        stages = SleepStages(deep_hours=1.5, rem_hours=2.0, light_hours=4.0)
        score = calculate_sleep_score(
            duration_hours=7.5,
            efficiency=90,
            stages=stages,
            date="2026-03-14",
        )
        assert score.total_score >= 80
        assert score.rating == "Excellent"
    
    def test_poor_sleep(self):
        """Poor sleep should score low."""
        score = calculate_sleep_score(
            duration_hours=4.0,
            efficiency=60,
            stages=None,
            date="2026-03-14",
        )
        assert score.total_score < 55
        assert score.rating == "Poor"
    
    def test_without_stages(self):
        """Score should work without stage data."""
        score = calculate_sleep_score(
            duration_hours=7.0,
            efficiency=85,
            stages=None,
        )
        assert score.total_score > 0
        assert score.stages_score == 0
    
    def test_score_has_all_components(self):
        """Score should have all component scores."""
        score = calculate_sleep_score(
            duration_hours=7.5,
            efficiency=85,
            stages=SleepStages(1.5, 2.0, 4.0),
            date="2026-03-14",
        )
        assert score.date == "2026-03-14"
        assert score.duration_score > 0
        assert score.efficiency_score > 0
        assert score.stages_score > 0


class TestSleepScoreRating:
    """Tests for rating text."""
    
    def test_excellent_rating(self):
        """85+ is excellent."""
        score = SleepScore(
            date="",
            total_score=90,
            duration_score=100,
            efficiency_score=100,
            stages_score=0,
            duration_hours=8,
            efficiency=90,
        )
        assert score.rating == "Excellent"
    
    def test_good_rating(self):
        """70-84 is good."""
        score = SleepScore(
            date="",
            total_score=75,
            duration_score=80,
            efficiency_score=80,
            stages_score=0,
            duration_hours=7,
            efficiency=85,
        )
        assert score.rating == "Good"
    
    def test_fair_rating(self):
        """55-69 is fair."""
        score = SleepScore(
            date="",
            total_score=60,
            duration_score=60,
            efficiency_score=70,
            stages_score=0,
            duration_hours=6,
            efficiency=75,
        )
        assert score.rating == "Fair"
    
    def test_poor_rating(self):
        """Below 55 is poor."""
        score = SleepScore(
            date="",
            total_score=40,
            duration_score=40,
            efficiency_score=50,
            stages_score=0,
            duration_hours=4,
            efficiency=60,
        )
        assert score.rating == "Poor"


class TestGetSleepTrend:
    """Tests for trend analysis."""
    
    def test_improving_trend(self):
        """Scores going up should be improving."""
        scores = [
            SleepScore("", 60, 60, 60, 0, 7, 80),
            SleepScore("", 65, 65, 65, 0, 7, 82),
            SleepScore("", 70, 70, 70, 0, 7.5, 85),
            SleepScore("", 80, 80, 80, 0, 8, 90),
        ]
        trend = get_sleep_trend(scores)
        assert trend["direction"] == "improving"
        assert trend["change"] > 0
    
    def test_declining_trend(self):
        """Scores going down should be declining."""
        scores = [
            SleepScore("", 85, 85, 85, 0, 8, 90),
            SleepScore("", 75, 75, 75, 0, 7, 85),
            SleepScore("", 65, 65, 65, 0, 6.5, 80),
            SleepScore("", 55, 55, 55, 0, 6, 75),
        ]
        trend = get_sleep_trend(scores)
        assert trend["direction"] == "declining"
        assert trend["change"] < 0
    
    def test_stable_trend(self):
        """Consistent scores should be stable."""
        scores = [
            SleepScore("", 75, 75, 75, 0, 7, 85),
            SleepScore("", 76, 76, 76, 0, 7, 85),
            SleepScore("", 74, 74, 74, 0, 7, 85),
            SleepScore("", 75, 75, 75, 0, 7, 85),
        ]
        trend = get_sleep_trend(scores)
        assert trend["direction"] == "stable"
    
    def test_insufficient_data(self):
        """Single score should return insufficient data."""
        scores = [SleepScore("", 75, 75, 75, 0, 7, 85)]
        trend = get_sleep_trend(scores)
        assert trend["direction"] == "insufficient_data"


class TestFormatSleepReport:
    """Tests for report formatting."""
    
    def test_basic_report(self):
        """Report should contain key information."""
        score = SleepScore(
            date="2026-03-14",
            total_score=80,
            duration_score=85,
            efficiency_score=90,
            stages_score=70,
            duration_hours=7.5,
            efficiency=88,
            stages=SleepStages(1.5, 2.0, 4.0),
        )
        report = format_sleep_report(score)
        
        assert "2026-03-14" in report
        assert "80" in report
        assert "Duration" in report
        assert "Efficiency" in report
        assert "Deep" in report
        assert "REM" in report
    
    def test_report_without_stages(self):
        """Report should work without stage data."""
        score = SleepScore(
            date="2026-03-14",
            total_score=75,
            duration_score=80,
            efficiency_score=85,
            stages_score=0,
            duration_hours=7.0,
            efficiency=85,
            stages=None,
        )
        report = format_sleep_report(score)
        
        assert "2026-03-14" in report
        assert "75" in report
        # Should not have Deep/REM when no stages
        assert "Deep" not in report
