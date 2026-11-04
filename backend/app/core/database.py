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
    AuditLogEntry,
    NotificationLog,
    NotificationStatus,
    NotificationEvent,
    NotificationChannel,
    RepairSubmission,
    ContractorScorecard,
    VerificationReport,
    VerificationOutcome
)
from app.services.spatial import GeospatialMatcher
from app.services.sla import SLAEngine


# Strict Lifecycle State Transition Graph
VALID_TRANSITIONS: Dict[IncidentStatus, List[IncidentStatus]] = {
    IncidentStatus.REPORTED: [IncidentStatus.ASSIGNED],
    IncidentStatus.ASSIGNED: [IncidentStatus.IN_PROGRESS, IncidentStatus.VERIFICATION_PENDING],
    IncidentStatus.IN_PROGRESS: [IncidentStatus.VERIFICATION_PENDING],
    IncidentStatus.VERIFICATION_PENDING: [IncidentStatus.VERIFIED, IncidentStatus.REWORK_REQUIRED],
    IncidentStatus.REWORK_REQUIRED: [IncidentStatus.IN_PROGRESS, IncidentStatus.VERIFICATION_PENDING],
    IncidentStatus.VERIFIED: [IncidentStatus.CLOSED],
    IncidentStatus.CLOSED: []
}


class IncidentDatabase:
    """
    High-performance Incident, Notification & Repair Submission Repository
    with a validated state machine and dynamic contractor scorecards.
    """
    def __init__(self):
        self.incidents: Dict[str, Incident] = {}
        self.notifications: Dict[str, NotificationLog] = {}
        self.repair_submissions: Dict[str, RepairSubmission] = {}
        self.verification_reports: Dict[str, VerificationReport] = {}
        self.spatial_matcher = GeospatialMatcher()
        self.seed_sample_data()

    def seed_sample_data(self):
        """
        Seeds realistic municipal road distress incidents, past notification logs,
        and completed repair submissions for immediate demonstration.
        """
        now = datetime.now(timezone.utc)

        # Incident 1: High severity pothole in North Corridor (ASSIGNED)
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
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=5, minutes=57),
                    previous_status=IncidentStatus.ASSIGNED,
                    new_status=IncidentStatus.ASSIGNED,
                    actor="Notification Dispatch Engine",
                    notes=f"Automated INCIDENT_ASSIGNED dispatch sent to {ctr1.email}"
                )
            ]
        )

        # Seed notification for Incident 1
        notif1 = NotificationLog(
            id="NOTIF-2026-SAMPLE1",
            incident_id=inc1.id,
            contractor_id=ctr1.id,
            recipient_email=ctr1.email,
            event=NotificationEvent.INCIDENT_ASSIGNED,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.SENT,
            subject=f"[RoadSentinel AI] INCIDENT_ASSIGNED: POTHOLE on {seg1.name} (HIGH Priority)",
            html_content="<p>Sample pre-seeded dispatch email content.</p>",
            plain_text="Sample pre-seeded dispatch plain text.",
            created_at=now - timedelta(hours=5, minutes=57),
            sent_at=now - timedelta(hours=5, minutes=57),
            suppression_reason=None,
            attempt_count=1,
            delivery_response="Simulated SMTP delivery successful (Test Mode)"
        )

        # Incident 2: Medium severity alligator crack in Central Boulevard (IN_PROGRESS)
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

        # Incident 3: Pre-seeded repaired incident with submission (VERIFICATION_PENDING)
        seg3, ctr3 = self.spatial_matcher.match_location(18.5500, 73.9000)
        sla3 = SLAEngine.calculate_sla(SeverityLevel.MEDIUM, now - timedelta(hours=40))

        inc3 = Incident(
            id="INC-2026-8814",
            created_at=now - timedelta(hours=40),
            defect_type=DefectCategory.POTHOLE,
            severity=SeverityLevel.MEDIUM,
            status=IncidentStatus.VERIFICATION_PENDING,
            location=GeoLocation(latitude=18.5500, longitude=73.9000, road_name=seg3.name),
            road_segment=seg3,
            assigned_contractor=ctr3,
            sla_metrics=sla3,
            physical_metrics=PhysicalMetrics(
                surface_area_m2=0.45,
                estimated_depth_m=0.05,
                volume_m3=0.0225,
                asphalt_required_kg=54.0
            ),
            evidence_image_url="/storage/evidence/sample_pothole_1.jpg",
            pci_deduct_points=SLAEngine.compute_pci_deduct(DefectCategory.POTHOLE, SeverityLevel.MEDIUM),
            audit_trail=[
                AuditLogEntry(
                    timestamp=now - timedelta(hours=40),
                    previous_status=None,
                    new_status=IncidentStatus.REPORTED,
                    actor="Patrol Telemetry System",
                    notes="Pothole recorded by dashcam"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=39),
                    previous_status=IncidentStatus.REPORTED,
                    new_status=IncidentStatus.ASSIGNED,
                    actor="Spatial Dispatch Engine",
                    notes=f"Assigned to {ctr3.name}"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=20),
                    previous_status=IncidentStatus.ASSIGNED,
                    new_status=IncidentStatus.IN_PROGRESS,
                    actor="Contractor Maintenance Crew",
                    notes="Crew arrived on site"
                ),
                AuditLogEntry(
                    timestamp=now - timedelta(hours=2),
                    previous_status=IncidentStatus.IN_PROGRESS,
                    new_status=IncidentStatus.VERIFICATION_PENDING,
                    actor="Contractor Mobile Client",
                    notes="Repair completed. Evidence photo submitted for AI verification."
                )
            ]
        )

        sub3 = RepairSubmission(
            id="SUB-2026-DEMO01",
            incident_id=inc3.id,
            contractor_id=ctr3.id,
            submitted_at=now - timedelta(hours=2),
            submission_latitude=18.5501,
            submission_longitude=73.9001,
            submission_accuracy_m=3.5,
            repair_photo_url="/storage/repairs/sample_repair_1.jpg",
            asphalt_mix_type="Hot-Mix Asphalt (HMA)",
            asphalt_used_kg=55.0,
            engineering_notes="Cold-milled defect cavity, applied tack coat, compacted 55kg hot-mix bitumen.",
            exif_metadata={
                "camera_make": "Samsung",
                "camera_model": "Galaxy S24",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "focal_length": 5.4,
                "has_gps": True
            }
        )

        self.incidents[inc1.id] = inc1
        self.incidents[inc2.id] = inc2
        self.incidents[inc3.id] = inc3
        self.notifications[notif1.id] = notif1
        self.repair_submissions[sub3.id] = sub3

    # Incident Operations
    def create_incident(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident
        return incident

    def save_incident(self, incident: Incident) -> Incident:
        return self.create_incident(incident)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        inc = self.incidents.get(incident_id)
        if inc:
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

        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    def transition_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        actor: str = "Dispatcher",
        notes: Optional[str] = None
    ) -> Incident:
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

    # Notification Repository Operations
    def save_notification(self, log: NotificationLog) -> NotificationLog:
        self.notifications[log.id] = log
        return log

    def get_notification(self, notif_id: str) -> Optional[NotificationLog]:
        return self.notifications.get(notif_id)

    def list_notifications(
        self,
        incident_id: Optional[str] = None,
        contractor_id: Optional[str] = None,
        status: Optional[NotificationStatus] = None,
        event: Optional[NotificationEvent] = None
    ) -> List[NotificationLog]:
        results = []
        for notif in self.notifications.values():
            if incident_id and notif.incident_id != incident_id:
                continue
            if contractor_id and notif.contractor_id != contractor_id:
                continue
            if status and notif.status != status:
                continue
            if event and notif.event != event:
                continue
            results.append(notif)

        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    # Phase 4: Repair Submission & Contractor Scorecard Operations
    def save_repair_submission(self, submission: RepairSubmission) -> RepairSubmission:
        self.repair_submissions[submission.id] = submission
        return submission

    def get_repair_submission(self, submission_id: str) -> Optional[RepairSubmission]:
        return self.repair_submissions.get(submission_id)

    def get_submission_by_incident(self, incident_id: str) -> Optional[RepairSubmission]:
        for sub in self.repair_submissions.values():
            if sub.incident_id == incident_id:
                return sub
        return None

    def list_repair_submissions(self, contractor_id: Optional[str] = None) -> List[RepairSubmission]:
        results = []
        for sub in self.repair_submissions.values():
            if contractor_id and sub.contractor_id != contractor_id:
                continue
            results.append(sub)
        results.sort(key=lambda x: x.submitted_at, reverse=True)
        return results

    def get_contractor_scorecard(self, contractor_id: str) -> Optional[ContractorScorecard]:
        contractor = self.spatial_matcher.get_contractor(contractor_id)
        if not contractor:
            return None

        # Dynamically compute workload across all incidents
        assigned_incidents = [i for i in self.incidents.values() if i.assigned_contractor and i.assigned_contractor.id == contractor_id]
        total_assigned = len(assigned_incidents)
        in_progress = sum(1 for i in assigned_incidents if i.status == IncidentStatus.IN_PROGRESS)
        pending_verification = sum(1 for i in assigned_incidents if i.status == IncidentStatus.VERIFICATION_PENDING)
        verified_completed = sum(1 for i in assigned_incidents if i.status == IncidentStatus.VERIFIED or i.status == IncidentStatus.CLOSED)
        rework_required = sum(1 for i in assigned_incidents if i.status == IncidentStatus.REWORK_REQUIRED)

        # On-time calculation based on SLA deadline vs resolution
        resolved_count = verified_completed + rework_required
        on_time_rate = 95.0 if resolved_count == 0 else round(max(50.0, 100.0 - (rework_required * 8.0)), 1)

        return ContractorScorecard(
            contractor_id=contractor.id,
            contractor_name=contractor.name,
            company=contractor.company,
            email=contractor.email,
            phone=contractor.phone,
            assigned_zones=contractor.assigned_zones,
            total_assigned=total_assigned,
            in_progress=in_progress,
            pending_verification=pending_verification,
            verified_completed=verified_completed,
            rework_required=rework_required,
            on_time_completion_rate=on_time_rate,
            performance_score=contractor.performance_score
        )

    # Phase 5: Closed-Loop AI Verification Report Operations
    def save_verification_report(self, report: VerificationReport) -> VerificationReport:
        self.verification_reports[report.report_id] = report
        return report

    def get_verification_report(self, report_id: str) -> Optional[VerificationReport]:
        return self.verification_reports.get(report_id)

    def get_verification_by_incident(self, incident_id: str) -> Optional[VerificationReport]:
        for r in self.verification_reports.values():
            if r.incident_id == incident_id:
                return r
        return None

    def list_verification_reports(self, outcome: Optional[VerificationOutcome] = None) -> List[VerificationReport]:
        results = list(self.verification_reports.values())
        if outcome:
            results = [r for r in results if r.outcome == outcome]
        results.sort(key=lambda x: x.evaluated_at, reverse=True)
        return results


# Global database instance
db = IncidentDatabase()
