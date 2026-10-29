import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    GeoLocation,
    PhysicalMetrics,
    AuditLogEntry
)
from app.services.spatial import GeospatialMatcher
from app.services.sla import SLAEngine


# Strict Lifecycle State Transition Graph
VALID_TRANSITIONS: Dict[IncidentStatus, List[IncidentStatus]] = {
    IncidentStatus.REPORTED: [IncidentStatus.ASSIGNED],
    IncidentStatus.ASSIGNED: [IncidentStatus.IN_PROGRESS],
    IncidentStatus.IN_PROGRESS: [IncidentStatus.VERIFICATION_PENDING],
    IncidentStatus.VERIFICATION_PENDING: [IncidentStatus.VERIFIED, IncidentStatus.REWORK_REQUIRED],
    IncidentStatus.REWORK_REQUIRED: [IncidentStatus.IN_PROGRESS],
    IncidentStatus.VERIFIED: [IncidentStatus.CLOSED],
    IncidentStatus.CLOSED: []
}


class IncidentDatabase:
    """
    High-performance Incident Repository with a validated state machine
    and immutable audit trails.
    """
    def __init__(self):
        self.incidents: Dict[str, Incident] = {}
        self.spatial_matcher = GeospatialMatcher()
        self.seed_sample_data()

    def seed_sample_data(self):
        """
        Seeds realistic municipal road distress incidents for immediate demonstration.
        """
        now = datetime.now(timezone.utc)

        # Incident 1: High severity pothole in North Corridor
        seg1, ctr1 = self.spatial_matcher.match_location(18.5204, 73.8567)
        sla1 = SLAEngine.calculate_sla(SeverityLevel.HIGH, now - timedelta(hours=6))

        inc1 = Incident(
            id="INC-2026-8812",
            created_at=now - timedelta(hours=6),
            defect_type=DefectCategory.POTHOLE,
            severity=SeverityLevel.HIGH,
            status=IncidentStatus.ASSIGNED,
            location=GeoLocation(latitude=18.5204, longitude=73.8567, road_name=seg1.name),
            road_segment=seg1,
            assigned_contractor=ctr1,
            sla_metrics=sla1,
            physical_metrics=PhysicalMetrics(
                surface_area_m2=0.55,
                estimated_depth_m=0.08,
                volume_m3=0.044,
                asphalt_required_kg=105.6
            ),
            evidence_image_url="/storage/evidence/sample_pothole_1.jpg",
            pci_deduct_points=SLAEngine.compute_pci_deduct(DefectCategory.POTHOLE, SeverityLevel.HIGH),
            audit_trail=[
                AuditLogEntry(
                    timestamp=now - timedelta(hours=6),
                    previous_status=None,
                    new_status=IncidentStatus.REPORTED,
                    actor="Patrol Telemetry System",
                    notes="Automated detection from video patrol run"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=5, minutes=58),
                    previous_status=IncidentStatus.REPORTED,
                    new_status=IncidentStatus.ASSIGNED,
                    actor="Spatial Dispatch Engine",
                    notes=f"Assigned to {ctr1.name} (Contract #{ctr1.id})"
                )
            ]
        )

        # Incident 2: Medium severity alligator crack in Central Boulevard
        seg2, ctr2 = self.spatial_matcher.match_location(18.5085, 73.8340)
        sla2 = SLAEngine.calculate_sla(SeverityLevel.MEDIUM, now - timedelta(hours=28))

        inc2 = Incident(
            id="INC-2026-8813",
            created_at=now - timedelta(hours=28),
            defect_type=DefectCategory.ALLIGATOR_CRACK,
            severity=SeverityLevel.MEDIUM,
            status=IncidentStatus.IN_PROGRESS,
            location=GeoLocation(latitude=18.5085, longitude=73.8340, road_name=seg2.name),
            road_segment=seg2,
            assigned_contractor=ctr2,
            sla_metrics=sla2,
            physical_metrics=PhysicalMetrics(
                surface_area_m2=1.20,
                estimated_depth_m=0.05,
                volume_m3=0.060,
                asphalt_required_kg=144.0
            ),
            evidence_image_url="/storage/evidence/sample_pothole_2.jpg",
            pci_deduct_points=SLAEngine.compute_pci_deduct(DefectCategory.ALLIGATOR_CRACK, SeverityLevel.MEDIUM),
            audit_trail=[
                AuditLogEntry(
                    timestamp=now - timedelta(hours=28),
                    previous_status=None,
                    new_status=IncidentStatus.REPORTED,
                    actor="Patrol Telemetry System",
                    notes="Surface fissure detected"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=27, minutes=50),
                    previous_status=IncidentStatus.REPORTED,
                    new_status=IncidentStatus.ASSIGNED,
                    actor="Spatial Dispatch Engine",
                    notes=f"Assigned to {ctr2.name}"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=14),
                    previous_status=IncidentStatus.ASSIGNED,
                    new_status=IncidentStatus.IN_PROGRESS,
                    actor="Contractor Mobile Client",
                    notes="Maintenance crew dispatched to site"
                )
            ]
        )

        self.incidents[inc1.id] = inc1
        self.incidents[inc2.id] = inc2

    def create_incident(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident
        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        inc = self.incidents.get(incident_id)
        if inc:
            # Refresh live SLA remaining hours
            inc.sla_metrics = SLAEngine.calculate_sla(inc.severity, inc.created_at)
        return inc

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[SeverityLevel] = None,
        contractor_id: Optional[str] = None,
        segment_id: Optional[str] = None
    ) -> List[Incident]:
        results = []
        for inc in self.incidents.values():
            # Refresh live SLA status
            inc.sla_metrics = SLAEngine.calculate_sla(inc.severity, inc.created_at)

            if status and inc.status != status:
                continue
            if severity and inc.severity != severity:
                continue
            if contractor_id and (not inc.assigned_contractor or inc.assigned_contractor.id != contractor_id):
                continue
            if segment_id and inc.road_segment.segment_id != segment_id:
                continue
            results.append(inc)

        # Sort by creation time descending (newest first)
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    def transition_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        actor: str = "Dispatcher",
        notes: Optional[str] = None
    ) -> Incident:
        """
        Validates state machine transitions against the strict state graph.
        Raises ValueError on illegal transitions.
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise KeyError(f"Incident with ID '{incident_id}' does not exist.")

        current_status = incident.status
        allowed_next = VALID_TRANSITIONS.get(current_status, [])

        if new_status not in allowed_next:
            raise ValueError(
                f"Illegal state transition: Cannot change from '{current_status.value}' to '{new_status.value}'. "
                f"Valid next states are: {[s.value for s in allowed_next]}"
            )

        # Apply state transition
        incident.status = new_status
        now = datetime.now(timezone.utc)
        incident.audit_trail.append(AuditLogEntry(
            timestamp=now,
            previous_status=current_status,
            new_status=new_status,
            actor=actor,
            notes=notes
        ))

        return incident


# Global database instance
db = IncidentDatabase()

