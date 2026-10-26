from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    GeoCoordinates,
    Contractor,
    VerificationReport
)
from app.services.spatial import SAMPLE_CONTRACTORS


class InMemoryStore:
    """
    High-performance in-memory repository with support for seed demo incidents.
    Can be seamlessly mirrored with SQLAlchemy/PostGIS.
    """
    def __init__(self):
        self.incidents: Dict[str, Incident] = {}
        self.contractors: Dict[str, Contractor] = {c.id: c for c in SAMPLE_CONTRACTORS}
        self.verifications: Dict[str, VerificationReport] = {}
        self._seed_sample_incidents()

    def _seed_sample_incidents(self):
        now = datetime.utcnow()
        sample_1 = Incident(
            id="INC-2026-8812",
            created_at=now - timedelta(hours=14),
            coordinates=GeoCoordinates(
                latitude=18.5204,
                longitude=73.8567,
                accuracy_m=3.5,
                road_name="State Highway 17 North (KM 14.2)"
            ),
            defect_type=DefectCategory.POTHOLE,
            severity=SeverityLevel.HIGH,
            status=IncidentStatus.ASSIGNED,
            assigned_contractor=self.contractors["CTR-001"],
            sla_deadline=now + timedelta(hours=10),
            evidence_image_url="/storage/evidence/sample_pothole_1.jpg",
            estimated_volume_m3=0.048,
            estimated_asphalt_kg=115.2,
            pci_impact=14.0
        )

        sample_2 = Incident(
            id="INC-2026-8813",
            created_at=now - timedelta(days=2),
            coordinates=GeoCoordinates(
                latitude=18.5085,
                longitude=73.8340,
                accuracy_m=4.0,
                road_name="Central Boulevard & Ring Road"
            ),
            defect_type=DefectCategory.ALLIGATOR_CRACK,
            severity=SeverityLevel.MEDIUM,
            status=IncidentStatus.IN_PROGRESS,
            assigned_contractor=self.contractors["CTR-002"],
            sla_deadline=now + timedelta(hours=22),
            evidence_image_url="/storage/evidence/sample_pothole_2.jpg",
            estimated_volume_m3=0.025,
            estimated_asphalt_kg=60.0,
            pci_impact=8.5
        )

        self.incidents[sample_1.id] = sample_1
        self.incidents[sample_2.id] = sample_2

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)

    def list_incidents(self, status: Optional[IncidentStatus] = None) -> List[Incident]:
        if status:
            return [inc for inc in self.incidents.values() if inc.status == status]
        return list(self.incidents.values())

    def create_incident(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident
        return incident

    def update_status(self, incident_id: str, new_status: IncidentStatus) -> Optional[Incident]:
        inc = self.incidents.get(incident_id)
        if inc:
            inc.status = new_status
        return inc

    def save_verification(self, report: VerificationReport):
        self.verifications[report.incident_id] = report


# Global instance
db = InMemoryStore()
