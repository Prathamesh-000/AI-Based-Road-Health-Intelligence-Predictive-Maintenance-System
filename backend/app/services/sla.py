from datetime import datetime, timedelta, timezone
from app.models.schemas import (
    SeverityLevel,
    DefectCategory,
    SLAMetrics,
    SLAStatus
)


# SLA Allowed Hours Table
SLA_HOURS_MAPPING = {
    SeverityLevel.CRITICAL: 12,
    SeverityLevel.HIGH: 24,
    SeverityLevel.MEDIUM: 72,
    SeverityLevel.LOW: 168
}

# ASTM D6433 PCI Deduct Values
PCI_DEDUCT_MAPPING = {
    (DefectCategory.POTHOLE, SeverityLevel.HIGH): 15.0,
    (DefectCategory.POTHOLE, SeverityLevel.MEDIUM): 9.0,
    (DefectCategory.POTHOLE, SeverityLevel.LOW): 4.0,
    (DefectCategory.ALLIGATOR_CRACK, SeverityLevel.HIGH): 12.0,
    (DefectCategory.ALLIGATOR_CRACK, SeverityLevel.MEDIUM): 7.0,
    (DefectCategory.ALLIGATOR_CRACK, SeverityLevel.LOW): 3.0,
    (DefectCategory.LONGITUDINAL_CRACK, SeverityLevel.HIGH): 8.0,
    (DefectCategory.LONGITUDINAL_CRACK, SeverityLevel.MEDIUM): 4.5,
    (DefectCategory.LONGITUDINAL_CRACK, SeverityLevel.LOW): 2.0,
    (DefectCategory.MANHOLE_DEPRESSION, SeverityLevel.HIGH): 10.0,
    (DefectCategory.MANHOLE_DEPRESSION, SeverityLevel.MEDIUM): 5.0,
    (DefectCategory.MANHOLE_DEPRESSION, SeverityLevel.LOW): 2.5,
}


class SLAEngine:
    """
    Dynamic SLA Calculation, Escalation Tracking, and PCI Impact Engine.
    """
    @staticmethod
    def calculate_sla(severity: SeverityLevel, created_at: datetime) -> SLAMetrics:
        """
        Computes dynamic deadline and current live SLA health status.
        """
        allowed_hours = SLA_HOURS_MAPPING.get(severity, 72)
        deadline = created_at + timedelta(hours=allowed_hours)

        now = datetime.now(timezone.utc) if created_at.tzinfo else datetime.utcnow()
        remaining_seconds = (deadline - now).total_seconds()
        remaining_hours = round(remaining_seconds / 3600.0, 1)

        if remaining_hours < 0:
            status = SLAStatus.BREACHED
        elif remaining_hours <= (allowed_hours * 0.20):  # Final 20% window
            status = SLAStatus.AT_RISK
        else:
            status = SLAStatus.ON_SCHEDULE

        return SLAMetrics(
            severity=severity,
            allowed_hours=allowed_hours,
            deadline=deadline,
            status=status,
            remaining_hours=remaining_hours
        )

    @staticmethod
    def compute_pci_deduct(defect_type: DefectCategory, severity: SeverityLevel) -> float:
        """
        Returns standard deduct points based on ASTM D6433 road distress ratings.
        """
        return PCI_DEDUCT_MAPPING.get((defect_type, severity), 6.0)

