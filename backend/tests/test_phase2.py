import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.schemas import (
    SeverityLevel,
    DefectCategory,
    IncidentStatus,
    SLAStatus,
    CreateIncidentFromDetectionRequest,
    UpdateIncidentStatusRequest
)
from app.services.spatial import GeospatialMatcher
from app.services.sla import SLAEngine
from app.core.database import db


def test_spatial_matching():
    print("[1/4] Testing Geospatial Boundary Matcher...")
    matcher = GeospatialMatcher()

    # 1. State Highway 17 North coordinate
    seg1, ctr1 = matcher.match_location(18.5204, 73.8567)
    print(f"  -> Point (18.5204, 73.8567) matched to '{seg1.name}' ({seg1.segment_id})")
    print(f"  -> Assigned Contractor: {ctr1.name} ({ctr1.id})")
    assert seg1.segment_id == "SEG-101", "Expected SEG-101"
    assert ctr1.id == "CTR-001", "Expected CTR-001"

    # 2. Central Boulevard coordinate
    seg2, ctr2 = matcher.match_location(18.5085, 73.8340)
    print(f"  -> Point (18.5085, 73.8340) matched to '{seg2.name}' ({seg2.segment_id})")
    assert seg2.segment_id == "SEG-102", "Expected SEG-102"
    assert ctr2.id == "CTR-002", "Expected CTR-002"

    # 3. Eastern Industrial Bypass coordinate
    seg3, ctr3 = matcher.match_location(18.5500, 73.9000)
    print(f"  -> Point (18.5500, 73.9000) matched to '{seg3.name}' ({seg3.segment_id})")
    assert seg3.segment_id == "SEG-103", "Expected SEG-103"
    assert ctr3.id == "CTR-003", "Expected CTR-003"

    print("  -> Geospatial matching tests PASSED.")


def test_dynamic_sla_engine():
    print("\n[2/4] Testing Dynamic SLA & PCI Deduct Engine...")
    now = datetime.now(timezone.utc)

    # 1. High severity pothole (24h allowed)
    sla_high = SLAEngine.calculate_sla(SeverityLevel.HIGH, now)
    print(f"  -> HIGH severity allowed hours: {sla_high.allowed_hours}h, status: {sla_high.status.value}")
    assert sla_high.allowed_hours == 24, "HIGH severity must have 24h SLA"
    assert sla_high.status == SLAStatus.ON_SCHEDULE

    # 2. Medium severity crack (72h allowed)
    sla_med = SLAEngine.calculate_sla(SeverityLevel.MEDIUM, now)
    assert sla_med.allowed_hours == 72, "MEDIUM severity must have 72h SLA"

    # 3. Test AT_RISK status (created 21 hours ago with 24h SLA)
    sla_at_risk = SLAEngine.calculate_sla(SeverityLevel.HIGH, now - timedelta(hours=21))
    print(f"  -> Ticket created 21h ago status: {sla_at_risk.status.value} (Remaining: {sla_at_risk.remaining_hours}h)")
    assert sla_at_risk.status == SLAStatus.AT_RISK, "Expected AT_RISK status"

    # 4. Test BREACHED status (created 30 hours ago with 24h SLA)
    sla_breached = SLAEngine.calculate_sla(SeverityLevel.HIGH, now - timedelta(hours=30))
    print(f"  -> Ticket created 30h ago status: {sla_breached.status.value}")
    assert sla_breached.status == SLAStatus.BREACHED, "Expected BREACHED status"

    # 5. ASTM D6433 PCI deduct points
    pci_deduct = SLAEngine.compute_pci_deduct(DefectCategory.POTHOLE, SeverityLevel.HIGH)
    print(f"  -> ASTM D6433 PCI deduct for HIGH pothole: {pci_deduct} points")
    assert pci_deduct == 15.0

    print("  -> Dynamic SLA engine tests PASSED.")


def test_state_machine_transitions():
    print("\n[3/4] Testing Incident State Machine & Transition Rules...")
    # Get seeded test incident
    inc = db.get_incident("INC-2026-8812")
    assert inc is not None, "Seeded incident INC-2026-8812 not found"
    assert inc.status == IncidentStatus.ASSIGNED

    # 1. Valid Transition: ASSIGNED -> IN_PROGRESS
    updated = db.transition_status(
        incident_id="INC-2026-8812",
        new_status=IncidentStatus.IN_PROGRESS,
        actor="Contractor Mobile Dispatch",
        notes="Repair crew arrived on site"
    )
    print(f"  -> Valid transition: ASSIGNED -> {updated.status.value}")
    assert updated.status == IncidentStatus.IN_PROGRESS
    assert len(updated.audit_trail) >= 3

    # 2. Valid Transition: IN_PROGRESS -> VERIFICATION_PENDING
    updated2 = db.transition_status(
        incident_id="INC-2026-8812",
        new_status=IncidentStatus.VERIFICATION_PENDING,
        actor="Contractor Mobile Dispatch",
        notes="Hot-mix asphalt patch applied, photo submitted"
    )
    print(f"  -> Valid transition: IN_PROGRESS -> {updated2.status.value}")
    assert updated2.status == IncidentStatus.VERIFICATION_PENDING

    # 3. Invalid Transition: Attempting VERIFICATION_PENDING -> CLOSED directly (Must be rejected!)
    try:
        db.transition_status(
            incident_id="INC-2026-8812",
            new_status=IncidentStatus.CLOSED,
            actor="Illegal Actor"
        )
        assert False, "State machine failed to reject illegal transition!"
    except ValueError as e:
        print(f"  -> Illegal transition correctly rejected by State Machine:")
        print(f"     '{e}'")

    print("  -> State machine transition tests PASSED.")


def test_create_from_phase1_detection():
    print("\n[4/4] Testing Promotion of Phase 1 Detection to Phase 2 Incident Ticket...")
    from app.api.routes_incidents import create_incident_from_detection_service

    # Simulate output received from Phase 1
    req = CreateIncidentFromDetectionRequest(
        defect_type=DefectCategory.POTHOLE,
        severity=SeverityLevel.HIGH,
        latitude=18.520432,
        longitude=73.856714,
        road_name="State Highway 17 North",
        surface_area_m2=0.48,
        estimated_depth_m=0.08,
        volume_m3=0.0384,
        asphalt_required_kg=92.16,
        evidence_image_url="/storage/evidence/defect_tr1_sharp.jpg"
    )

    created_incident = create_incident_from_detection_service(req)
    print(f"  -> Generated Incident ID: {created_incident.id}")
    print(f"  -> Status: {created_incident.status.value}")
    print(f"  -> Matched Road: {created_incident.road_segment.name} ({created_incident.road_segment.zone})")
    print(f"  -> Assigned Contractor: {created_incident.assigned_contractor.name}")
    print(f"  -> SLA Deadline: {created_incident.sla_metrics.deadline.isoformat()} ({created_incident.sla_metrics.allowed_hours}h)")
    print(f"  -> Asphalt Material Required: {created_incident.physical_metrics.asphalt_required_kg} kg")

    assert created_incident.id.startswith("INC-2026-")
    assert created_incident.status == IncidentStatus.ASSIGNED
    assert created_incident.assigned_contractor.id == "CTR-001"
    assert created_incident.sla_metrics.allowed_hours == 24

    print("  -> Phase 1 to Phase 2 pipeline bridge PASSED.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("==========================================================")
    print(" [TEST] RUNNING PHASE 2 TEST SUITE: RoadSentinel AI")
    print("==========================================================")
    test_spatial_matching()
    test_dynamic_sla_engine()
    test_state_machine_transitions()
    test_create_from_phase1_detection()
    print("\n[SUCCESS] ALL PHASE 2 TESTS COMPLETED WITH 100% SUCCESS!")
