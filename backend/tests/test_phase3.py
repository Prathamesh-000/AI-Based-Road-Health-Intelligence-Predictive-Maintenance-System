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
    NotificationStatus,
    NotificationEvent,
    NotificationChannel,
    CreateIncidentFromDetectionRequest,
    DispatchIncidentRequest
)
from app.core.database import db
from app.services.notification import (
    NotificationTemplateRenderer,
    NotificationSuppressionEngine,
    notification_dispatcher
)
from app.api.routes_incidents import create_incident_from_detection_service


def test_template_rendering():
    print("[1/4] Testing HTML & Plaintext Template Rendering...")
    incident = db.get_incident("INC-2026-8812")
    assert incident is not None, "Seeded incident INC-2026-8812 not found"

    # Render HTML
    html = NotificationTemplateRenderer.render_html(
        incident=incident,
        event=NotificationEvent.INCIDENT_ASSIGNED,
        custom_notes="Urgent arterial lane repair"
    )

    # Render Plain Text
    plain_text = NotificationTemplateRenderer.render_plain_text(
        incident=incident,
        event=NotificationEvent.INCIDENT_ASSIGNED,
        custom_notes="Urgent arterial lane repair"
    )

    # Assertions on HTML
    assert "<!DOCTYPE html>" in html
    assert incident.id in html
    assert incident.road_segment.name in html
    assert f"{incident.physical_metrics.asphalt_required_kg:.1f} kg" in html
    assert f"{incident.sla_metrics.allowed_hours} Hours" in html
    assert "https://maps.google.com/?q=" in html
    assert "Urgent arterial lane repair" in html

    # Assertions on Plain Text
    assert incident.id in plain_text
    assert "QUANTIFICATION" in plain_text
    assert f"{incident.physical_metrics.asphalt_required_kg:.1f} kg" in plain_text

    print(f"  -> HTML Template successfully compiled ({len(html)} bytes).")
    print(f"  -> Plaintext Template successfully compiled ({len(plain_text)} bytes).")
    print("  -> Template rendering tests PASSED.")


def test_notification_dispatch_and_logging():
    print("\n[2/4] Testing Automated Notification Dispatch & Logging...")
    incident = db.get_incident("INC-2026-8813")
    assert incident is not None, "Seeded incident INC-2026-8813 not found"

    # Initial audit trail count
    initial_audit_len = len(incident.audit_trail)

    # Dispatch notification
    log = notification_dispatcher.dispatch_incident_notification(
        incident=incident,
        event=NotificationEvent.INCIDENT_ASSIGNED,
        channel=NotificationChannel.EMAIL,
        custom_notes="Initial contract work order dispatch"
    )

    print(f"  -> Dispatched Notification ID: {log.id}")
    print(f"  -> Recipient: {log.recipient_email}")
    print(f"  -> Delivery Status: {log.status.value}")
    print(f"  -> Response: {log.delivery_response}")

    assert log.id.startswith("NOTIF-2026-")
    assert log.status == NotificationStatus.SENT
    assert log.recipient_email == incident.assigned_contractor.email
    assert log.sent_at is not None
    assert len(incident.audit_trail) == initial_audit_len + 1

    # Verify notification is retrievable from database
    stored_notif = db.get_notification(log.id)
    assert stored_notif is not None
    assert stored_notif.id == log.id

    print("  -> Dispatch and audit logging tests PASSED.")


def test_notification_suppression_engine():
    print("\n[3/4] Testing Anti-Spam & Proximity Suppression Engine...")
    incident = db.get_incident("INC-2026-8813")
    assert incident is not None

    # Subtest 3A: Immediate duplicate dispatch on same incident (Must be SUPPRESSED)
    duplicate_log = notification_dispatcher.dispatch_incident_notification(
        incident=incident,
        event=NotificationEvent.INCIDENT_ASSIGNED,
        channel=NotificationChannel.EMAIL,
        force_resend=False
    )

    print(f"  -> Duplicate dispatch status: {duplicate_log.status.value}")
    print(f"  -> Suppression Reason: {duplicate_log.suppression_reason}")
    assert duplicate_log.status == NotificationStatus.SUPPRESSED
    assert "Duplicate alert" in duplicate_log.suppression_reason

    # Subtest 3B: Force Resend Override (Must be SENT)
    forced_log = notification_dispatcher.dispatch_incident_notification(
        incident=incident,
        event=NotificationEvent.INCIDENT_ASSIGNED,
        channel=NotificationChannel.EMAIL,
        force_resend=True
    )
    print(f"  -> Force resend status: {forced_log.status.value}")
    assert forced_log.status == NotificationStatus.SENT

    # Subtest 3C: Spatial Proximity Suppression (Nearby defect <= 50m within cooling period)
    # Create another defect within 15 meters on the same road segment
    nearby_req = CreateIncidentFromDetectionRequest(
        defect_type=DefectCategory.POTHOLE,
        severity=SeverityLevel.HIGH,
        latitude=incident.location.latitude + 0.0001,  # ~11 meters away
        longitude=incident.location.longitude + 0.0001,
        road_name=incident.road_segment.name,
        surface_area_m2=0.35,
        estimated_depth_m=0.08,
        volume_m3=0.028,
        asphalt_required_kg=67.2,
        evidence_image_url="/storage/evidence/sample_pothole_nearby.jpg"
    )

    # Creating this incident will auto-evaluate proximity suppression!
    nearby_incident = create_incident_from_detection_service(nearby_req, dispatch_alert=True)
    print(f"  -> Created nearby incident: {nearby_incident.id} (~15m from {incident.id})")

    # Check notification logs for this nearby incident
    nearby_notifs = db.list_notifications(incident_id=nearby_incident.id)
    assert len(nearby_notifs) >= 1
    nearby_notif = nearby_notifs[0]
    print(f"  -> Nearby incident notification status: {nearby_notif.status.value}")
    print(f"  -> Nearby suppression reason: {nearby_notif.suppression_reason}")

    assert nearby_notif.status == NotificationStatus.SUPPRESSED
    assert "Notification cooling active" in nearby_notif.suppression_reason

    print("  -> Anti-spam and proximity suppression engine tests PASSED.")


def test_end_to_end_integration():
    print("\n[4/4] Testing End-to-End Promotion -> Dispatch -> Retrieval Pipeline...")
    # Clean new coordinate far away from other defects to ensure non-suppressed fresh dispatch
    req = CreateIncidentFromDetectionRequest(
        defect_type=DefectCategory.POTHOLE,
        severity=SeverityLevel.HIGH,
        latitude=18.5650,  # Eastern Bypass area, clear coordinates
        longitude=73.9150,
        road_name="Eastern Industrial Bypass",
        surface_area_m2=0.72,
        estimated_depth_m=0.08,
        volume_m3=0.0576,
        asphalt_required_kg=138.24,
        evidence_image_url="/storage/evidence/east_bypass_pothole.jpg"
    )

    incident = create_incident_from_detection_service(req, dispatch_alert=True)
    print(f"  -> Generated Incident: {incident.id} on {incident.road_segment.name}")
    print(f"  -> Assigned Contractor: {incident.assigned_contractor.name} ({incident.assigned_contractor.email})")

    # Verify notification was generated and sent
    notifs = db.list_notifications(incident_id=incident.id)
    assert len(notifs) >= 1
    dispatched = notifs[0]

    print(f"  -> Notification ID: {dispatched.id}")
    print(f"  -> Status: {dispatched.status.value}")
    print(f"  -> Delivery Response: {dispatched.delivery_response}")

    assert dispatched.status == NotificationStatus.SENT
    assert dispatched.recipient_email == incident.assigned_contractor.email
    assert dispatched.incident_id == incident.id

    # Check that incident audit trail has dispatch recorded
    has_dispatch_audit = any("Notification Dispatch Engine" in entry.actor for entry in incident.audit_trail)
    assert has_dispatch_audit, "Incident audit trail missing notification dispatch record"

    print("  -> End-to-end promotion, dispatch, and retrieval tests PASSED.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("==========================================================")
    print(" [TEST] RUNNING PHASE 3 TEST SUITE: RoadSentinel AI")
    print("==========================================================")
    test_template_rendering()
    test_notification_dispatch_and_logging()
    test_notification_suppression_engine()
    test_end_to_end_integration()
    print("\n[SUCCESS] ALL PHASE 3 TESTS COMPLETED WITH 100% SUCCESS!")

