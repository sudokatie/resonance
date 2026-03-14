"""Tests for medication tracking."""

import pytest
from datetime import datetime, date, time, timedelta
from pathlib import Path
import tempfile
import shutil

from resonance.analysis.medication import (
    Medication,
    DoseLog,
    AdherenceStats,
    Frequency,
    MedicationTracker,
    format_adherence_report,
    format_schedule,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def tracker(temp_config_dir):
    """Create a tracker with temp config."""
    return MedicationTracker(config_dir=temp_config_dir)


class TestMedication:
    """Tests for Medication dataclass."""
    
    def test_create_medication(self):
        """Create a basic medication."""
        med = Medication(
            name="Aspirin",
            dosage="100mg",
            frequency=Frequency.ONCE_DAILY,
            scheduled_times=[time(8, 0)],
        )
        assert med.name == "Aspirin"
        assert med.active is True
    
    def test_expected_doses_once_daily(self):
        """Once daily should expect 1 dose."""
        med = Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.ONCE_DAILY,
            scheduled_times=[time(9, 0)],
        )
        assert med.expected_doses_per_day() == 1
    
    def test_expected_doses_twice_daily(self):
        """Twice daily should expect 2 doses."""
        med = Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.TWICE_DAILY,
            scheduled_times=[time(8, 0), time(20, 0)],
        )
        assert med.expected_doses_per_day() == 2
    
    def test_expected_doses_as_needed(self):
        """As-needed should return 0."""
        med = Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.AS_NEEDED,
        )
        assert med.expected_doses_per_day() == 0


class TestDoseLog:
    """Tests for DoseLog dataclass."""
    
    def test_create_dose_log(self):
        """Create a dose log entry."""
        now = datetime.now()
        dose = DoseLog(
            medication_id=1,
            taken_at=now,
            scheduled_time=time(8, 0),
        )
        assert dose.medication_id == 1
        assert dose.skipped is False
    
    def test_skipped_dose(self):
        """Create a skipped dose entry."""
        dose = DoseLog(
            medication_id=1,
            taken_at=datetime.now(),
            skipped=True,
            notes="Felt sick",
        )
        assert dose.skipped is True
        assert dose.notes == "Felt sick"


class TestAdherenceStats:
    """Tests for AdherenceStats."""
    
    def test_excellent_rating(self):
        """95%+ should be excellent."""
        stats = AdherenceStats(
            medication_name="Test",
            total_expected=100,
            total_taken=96,
            total_skipped=2,
            total_missed=2,
            adherence_rate=96.0,
            period_days=30,
        )
        assert stats.rating == "Excellent"
    
    def test_good_rating(self):
        """80-94% should be good."""
        stats = AdherenceStats(
            medication_name="Test",
            total_expected=100,
            total_taken=85,
            total_skipped=5,
            total_missed=10,
            adherence_rate=85.0,
            period_days=30,
        )
        assert stats.rating == "Good"
    
    def test_fair_rating(self):
        """60-79% should be fair."""
        stats = AdherenceStats(
            medication_name="Test",
            total_expected=100,
            total_taken=70,
            total_skipped=10,
            total_missed=20,
            adherence_rate=70.0,
            period_days=30,
        )
        assert stats.rating == "Fair"
    
    def test_poor_rating(self):
        """Below 60% should be poor."""
        stats = AdherenceStats(
            medication_name="Test",
            total_expected=100,
            total_taken=50,
            total_skipped=10,
            total_missed=40,
            adherence_rate=50.0,
            period_days=30,
        )
        assert stats.rating == "Poor"


class TestMedicationTracker:
    """Tests for MedicationTracker."""
    
    def test_add_medication(self, tracker):
        """Add a medication."""
        med = Medication(
            name="Aspirin",
            dosage="100mg",
            frequency=Frequency.ONCE_DAILY,
            scheduled_times=[time(8, 0)],
        )
        added = tracker.add_medication(med)
        
        assert added.id is not None
        assert added.id == 1
    
    def test_list_medications(self, tracker):
        """List medications."""
        tracker.add_medication(Medication(
            name="Med1",
            dosage="10mg",
            frequency=Frequency.ONCE_DAILY,
        ))
        tracker.add_medication(Medication(
            name="Med2",
            dosage="20mg",
            frequency=Frequency.TWICE_DAILY,
        ))
        
        meds = tracker.list_medications()
        assert len(meds) == 2
    
    def test_get_medication_by_name(self, tracker):
        """Get medication by name."""
        tracker.add_medication(Medication(
            name="Aspirin",
            dosage="100mg",
            frequency=Frequency.ONCE_DAILY,
        ))
        
        med = tracker.get_medication_by_name("aspirin")  # case insensitive
        assert med is not None
        assert med.name == "Aspirin"
    
    def test_deactivate_medication(self, tracker):
        """Deactivate a medication."""
        med = tracker.add_medication(Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.ONCE_DAILY,
        ))
        
        tracker.deactivate_medication(med.id)
        
        # Should not appear in active list
        active = tracker.list_medications(active_only=True)
        assert len(active) == 0
        
        # Should appear in full list
        all_meds = tracker.list_medications(active_only=False)
        assert len(all_meds) == 1
    
    def test_log_dose(self, tracker):
        """Log a dose."""
        med = tracker.add_medication(Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.ONCE_DAILY,
            scheduled_times=[time(8, 0)],
        ))
        
        dose = tracker.log_dose(
            medication_id=med.id,
            scheduled_time=time(8, 0),
        )
        
        assert dose.id is not None
        assert dose.medication_id == med.id
    
    def test_get_doses_for_date(self, tracker):
        """Get doses for a specific date."""
        med = tracker.add_medication(Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.TWICE_DAILY,
        ))
        
        today = date.today()
        tracker.log_dose(med.id, taken_at=datetime.combine(today, time(8, 0)))
        tracker.log_dose(med.id, taken_at=datetime.combine(today, time(20, 0)))
        
        doses = tracker.get_doses_for_date(med.id, today)
        assert len(doses) == 2
    
    def test_calculate_adherence(self, tracker):
        """Calculate adherence statistics."""
        med = tracker.add_medication(Medication(
            name="Test",
            dosage="10mg",
            frequency=Frequency.ONCE_DAILY,
            scheduled_times=[time(8, 0)],
        ))
        
        # Log doses for the last 7 days
        today = date.today()
        for i in range(5):  # 5 out of 7 days
            dose_date = today - timedelta(days=i)
            tracker.log_dose(
                med.id,
                taken_at=datetime.combine(dose_date, time(8, 0)),
                scheduled_time=time(8, 0),
            )
        
        stats = tracker.calculate_adherence(med.id, days=7)
        
        assert stats is not None
        assert stats.total_expected == 7
        assert stats.total_taken == 5
        assert stats.adherence_rate == pytest.approx(71.4, rel=0.1)
    
    def test_persistence(self, temp_config_dir):
        """Data should persist across tracker instances."""
        tracker1 = MedicationTracker(config_dir=temp_config_dir)
        med = tracker1.add_medication(Medication(
            name="Persistent",
            dosage="50mg",
            frequency=Frequency.ONCE_DAILY,
        ))
        tracker1.log_dose(med.id)
        
        # Create new tracker, should load same data
        tracker2 = MedicationTracker(config_dir=temp_config_dir)
        
        meds = tracker2.list_medications()
        assert len(meds) == 1
        assert meds[0].name == "Persistent"


class TestFormatting:
    """Tests for formatting functions."""
    
    def test_format_adherence_report(self):
        """Format adherence report."""
        stats = AdherenceStats(
            medication_name="Aspirin",
            total_expected=30,
            total_taken=27,
            total_skipped=2,
            total_missed=1,
            adherence_rate=90.0,
            period_days=30,
        )
        
        report = format_adherence_report(stats)
        
        assert "Aspirin" in report
        assert "90%" in report
        assert "Good" in report
        assert "27" in report
    
    def test_format_schedule(self):
        """Format schedule."""
        med = Medication(
            name="TestMed",
            dosage="100mg",
            frequency=Frequency.ONCE_DAILY,
        )
        med.id = 1
        
        schedule = [
            (med, time(8, 0), False),
            (med, time(20, 0), True),
        ]
        
        output = format_schedule(schedule)
        
        assert "TestMed" in output
        assert "[ ]" in output  # untaken
        assert "[x]" in output  # taken
    
    def test_format_empty_schedule(self):
        """Format empty schedule."""
        output = format_schedule([])
        assert "No medications" in output
