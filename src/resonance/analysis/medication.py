"""Medication tracking and adherence analysis.

Track medication schedules, log doses taken, and analyze adherence rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import Optional, TYPE_CHECKING
import json
from pathlib import Path

if TYPE_CHECKING:
    from ..database import Database


class Frequency(Enum):
    """Medication dosing frequency."""
    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"
    AS_NEEDED = "as_needed"
    WEEKLY = "weekly"


@dataclass
class Medication:
    """A medication with its schedule."""
    name: str
    dosage: str
    frequency: Frequency
    scheduled_times: list[time] = field(default_factory=list)
    notes: str = ""
    active: bool = True
    id: Optional[int] = None
    
    def expected_doses_per_day(self) -> int:
        """Number of doses expected per day."""
        if self.frequency == Frequency.AS_NEEDED:
            return 0
        elif self.frequency == Frequency.WEEKLY:
            return 0  # Not daily
        else:
            return len(self.scheduled_times) if self.scheduled_times else {
                Frequency.ONCE_DAILY: 1,
                Frequency.TWICE_DAILY: 2,
                Frequency.THREE_TIMES_DAILY: 3,
                Frequency.FOUR_TIMES_DAILY: 4,
            }.get(self.frequency, 1)


@dataclass
class DoseLog:
    """A logged dose of medication."""
    medication_id: int
    taken_at: datetime
    scheduled_time: Optional[time] = None
    skipped: bool = False
    notes: str = ""
    id: Optional[int] = None


@dataclass
class AdherenceStats:
    """Adherence statistics for a medication."""
    medication_name: str
    total_expected: int
    total_taken: int
    total_skipped: int
    total_missed: int
    adherence_rate: float  # 0-100
    period_days: int
    
    @property
    def rating(self) -> str:
        """Get adherence rating."""
        if self.adherence_rate >= 95:
            return "Excellent"
        elif self.adherence_rate >= 80:
            return "Good"
        elif self.adherence_rate >= 60:
            return "Fair"
        else:
            return "Poor"


class MedicationTracker:
    """Track medications and adherence."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize tracker.
        
        Args:
            config_dir: Directory for config files. Defaults to ~/.config/resonance/
        """
        if config_dir is None:
            config_dir = Path.home() / ".config" / "resonance"
        
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.medications_file = config_dir / "medications.json"
        self.doses_file = config_dir / "dose_log.json"
        
        self._medications: list[Medication] = []
        self._doses: list[DoseLog] = []
        self._load()
    
    def _load(self) -> None:
        """Load data from files."""
        if self.medications_file.exists():
            try:
                data = json.loads(self.medications_file.read_text())
                self._medications = [self._medication_from_dict(m) for m in data]
            except (json.JSONDecodeError, KeyError):
                self._medications = []
        
        if self.doses_file.exists():
            try:
                data = json.loads(self.doses_file.read_text())
                self._doses = [self._dose_from_dict(d) for d in data]
            except (json.JSONDecodeError, KeyError):
                self._doses = []
    
    def _save(self) -> None:
        """Save data to files."""
        med_data = [self._medication_to_dict(m) for m in self._medications]
        self.medications_file.write_text(json.dumps(med_data, indent=2))
        
        dose_data = [self._dose_to_dict(d) for d in self._doses]
        self.doses_file.write_text(json.dumps(dose_data, indent=2))
    
    def _medication_to_dict(self, med: Medication) -> dict:
        """Convert medication to dict."""
        return {
            "id": med.id,
            "name": med.name,
            "dosage": med.dosage,
            "frequency": med.frequency.value,
            "scheduled_times": [t.isoformat() for t in med.scheduled_times],
            "notes": med.notes,
            "active": med.active,
        }
    
    def _medication_from_dict(self, data: dict) -> Medication:
        """Convert dict to medication."""
        times = [time.fromisoformat(t) for t in data.get("scheduled_times", [])]
        return Medication(
            id=data.get("id"),
            name=data["name"],
            dosage=data["dosage"],
            frequency=Frequency(data["frequency"]),
            scheduled_times=times,
            notes=data.get("notes", ""),
            active=data.get("active", True),
        )
    
    def _dose_to_dict(self, dose: DoseLog) -> dict:
        """Convert dose log to dict."""
        return {
            "id": dose.id,
            "medication_id": dose.medication_id,
            "taken_at": dose.taken_at.isoformat(),
            "scheduled_time": dose.scheduled_time.isoformat() if dose.scheduled_time else None,
            "skipped": dose.skipped,
            "notes": dose.notes,
        }
    
    def _dose_from_dict(self, data: dict) -> DoseLog:
        """Convert dict to dose log."""
        sched_time = None
        if data.get("scheduled_time"):
            sched_time = time.fromisoformat(data["scheduled_time"])
        return DoseLog(
            id=data.get("id"),
            medication_id=data["medication_id"],
            taken_at=datetime.fromisoformat(data["taken_at"]),
            scheduled_time=sched_time,
            skipped=data.get("skipped", False),
            notes=data.get("notes", ""),
        )
    
    def add_medication(self, medication: Medication) -> Medication:
        """Add a new medication.
        
        Args:
            medication: Medication to add
            
        Returns:
            Medication with assigned ID
        """
        # Assign ID
        max_id = max((m.id or 0) for m in self._medications) if self._medications else 0
        medication.id = max_id + 1
        
        self._medications.append(medication)
        self._save()
        return medication
    
    def update_medication(self, medication: Medication) -> None:
        """Update an existing medication."""
        for i, m in enumerate(self._medications):
            if m.id == medication.id:
                self._medications[i] = medication
                self._save()
                return
        raise ValueError(f"Medication with ID {medication.id} not found")
    
    def get_medication(self, medication_id: int) -> Optional[Medication]:
        """Get medication by ID."""
        for m in self._medications:
            if m.id == medication_id:
                return m
        return None
    
    def get_medication_by_name(self, name: str) -> Optional[Medication]:
        """Get medication by name (case-insensitive)."""
        name_lower = name.lower()
        for m in self._medications:
            if m.name.lower() == name_lower:
                return m
        return None
    
    def list_medications(self, active_only: bool = True) -> list[Medication]:
        """List all medications.
        
        Args:
            active_only: If True, only return active medications
        """
        if active_only:
            return [m for m in self._medications if m.active]
        return list(self._medications)
    
    def deactivate_medication(self, medication_id: int) -> None:
        """Deactivate a medication (soft delete)."""
        med = self.get_medication(medication_id)
        if med:
            med.active = False
            self._save()
    
    def log_dose(
        self,
        medication_id: int,
        taken_at: Optional[datetime] = None,
        scheduled_time: Optional[time] = None,
        skipped: bool = False,
        notes: str = "",
    ) -> DoseLog:
        """Log a dose taken or skipped.
        
        Args:
            medication_id: ID of the medication
            taken_at: When the dose was taken (defaults to now)
            scheduled_time: The scheduled time this dose was for
            skipped: Whether the dose was skipped
            notes: Optional notes
            
        Returns:
            The logged dose
        """
        if taken_at is None:
            taken_at = datetime.now()
        
        max_id = max((d.id or 0) for d in self._doses) if self._doses else 0
        
        dose = DoseLog(
            id=max_id + 1,
            medication_id=medication_id,
            taken_at=taken_at,
            scheduled_time=scheduled_time,
            skipped=skipped,
            notes=notes,
        )
        
        self._doses.append(dose)
        self._save()
        return dose
    
    def get_doses_for_date(
        self,
        medication_id: int,
        target_date: date,
    ) -> list[DoseLog]:
        """Get all doses for a medication on a specific date."""
        return [
            d for d in self._doses
            if d.medication_id == medication_id
            and d.taken_at.date() == target_date
        ]
    
    def get_doses_in_range(
        self,
        medication_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DoseLog]:
        """Get doses for a medication in a date range."""
        return [
            d for d in self._doses
            if d.medication_id == medication_id
            and start_date <= d.taken_at.date() <= end_date
        ]
    
    def calculate_adherence(
        self,
        medication_id: int,
        days: int = 7,
    ) -> Optional[AdherenceStats]:
        """Calculate adherence statistics.
        
        Args:
            medication_id: ID of the medication
            days: Number of days to analyze
            
        Returns:
            AdherenceStats or None if medication not found
        """
        med = self.get_medication(medication_id)
        if not med:
            return None
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        doses = self.get_doses_in_range(medication_id, start_date, end_date)
        
        # Calculate expected doses
        expected_per_day = med.expected_doses_per_day()
        if expected_per_day == 0:
            # As-needed or weekly - can't calculate adherence meaningfully
            return AdherenceStats(
                medication_name=med.name,
                total_expected=0,
                total_taken=len([d for d in doses if not d.skipped]),
                total_skipped=len([d for d in doses if d.skipped]),
                total_missed=0,
                adherence_rate=100.0 if doses else 0.0,
                period_days=days,
            )
        
        total_expected = expected_per_day * days
        total_taken = len([d for d in doses if not d.skipped])
        total_skipped = len([d for d in doses if d.skipped])
        total_missed = max(0, total_expected - total_taken - total_skipped)
        
        adherence_rate = (total_taken / total_expected * 100) if total_expected > 0 else 0.0
        
        return AdherenceStats(
            medication_name=med.name,
            total_expected=total_expected,
            total_taken=total_taken,
            total_skipped=total_skipped,
            total_missed=total_missed,
            adherence_rate=adherence_rate,
            period_days=days,
        )
    
    def get_today_schedule(self) -> list[tuple[Medication, time, bool]]:
        """Get today's medication schedule.
        
        Returns:
            List of (medication, scheduled_time, taken) tuples
        """
        today = date.today()
        schedule = []
        
        for med in self.list_medications():
            if not med.scheduled_times:
                continue
            
            today_doses = self.get_doses_for_date(med.id, today)
            taken_times = {d.scheduled_time for d in today_doses if d.scheduled_time}
            
            for sched_time in med.scheduled_times:
                taken = sched_time in taken_times
                schedule.append((med, sched_time, taken))
        
        # Sort by time
        schedule.sort(key=lambda x: x[1])
        return schedule
    
    def get_next_dose(self) -> Optional[tuple[Medication, time]]:
        """Get the next scheduled dose.
        
        Returns:
            Tuple of (medication, time) or None if no upcoming doses
        """
        now = datetime.now()
        current_time = now.time()
        today = now.date()
        
        schedule = self.get_today_schedule()
        
        # Find next untaken dose today
        for med, sched_time, taken in schedule:
            if not taken and sched_time > current_time:
                return (med, sched_time)
        
        # No more doses today - return first dose tomorrow
        tomorrow_schedule = []
        for med in self.list_medications():
            if med.scheduled_times:
                tomorrow_schedule.append((med, med.scheduled_times[0]))
        
        if tomorrow_schedule:
            tomorrow_schedule.sort(key=lambda x: x[1])
            return tomorrow_schedule[0]
        
        return None


def format_adherence_report(stats: AdherenceStats) -> str:
    """Format adherence stats as a text report.
    
    Args:
        stats: AdherenceStats to format
        
    Returns:
        Formatted string
    """
    lines = [
        f"Medication Adherence Report: {stats.medication_name}",
        "=" * 40,
        "",
        f"Period: Last {stats.period_days} days",
        f"Adherence Rate: {stats.adherence_rate:.0f}% ({stats.rating})",
        "",
        f"Doses Taken:   {stats.total_taken}",
        f"Doses Skipped: {stats.total_skipped}",
        f"Doses Missed:  {stats.total_missed}",
        f"Total Expected: {stats.total_expected}",
    ]
    
    return "\n".join(lines)


def format_schedule(schedule: list[tuple[Medication, time, bool]]) -> str:
    """Format today's schedule.
    
    Args:
        schedule: List from get_today_schedule()
        
    Returns:
        Formatted string
    """
    if not schedule:
        return "No medications scheduled for today."
    
    lines = ["Today's Medication Schedule", "=" * 30, ""]
    
    for med, sched_time, taken in schedule:
        status = "[x]" if taken else "[ ]"
        time_str = sched_time.strftime("%I:%M %p")
        lines.append(f"{status} {time_str} - {med.name} ({med.dosage})")
    
    return "\n".join(lines)
