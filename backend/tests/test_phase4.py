import sys
import io
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import cv2
from fastapi import UploadFile, HTTPException

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.schemas import (
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    ContractorScorecard,
    RepairSubmission
)
from app.core.database import db
from app.services.contractor import contractor_service
from app.core.config import REPAIRS_DIR


def test_contractor_scorecard():
    print("[1/5] Testing Contractor Scorecard & Workload Metrics...")
    scorecard = db.get_contractor_scorecard("CTR-001")
    assert scorecard is not None, "Contractor CTR-001 scorecard not found"

    print(f"  -> Contractor: {scorecard.contractor_name} ({scorecard.company})")
    print(f"  -> Zones: {', '.join(scorecard.assigned_zones)}")
    print(f"  -> Total Assigned: {scorecard.total_assigned}")
    print(f"  -> In Progress: {scorecard.in_progress}")
    print(f"  -> Verified Completed: {scorecard.verified_completed}")
    print(f"  -> On-Time Rate: {scorecard.on_time_completion_rate}%")
    print(f"  -> Rating: {scorecard.performance_score}/100")

    assert scorecard.contractor_id == "CTR-001"
    assert scorecard.total_assigned >= 1
    assert scorecard.on_time_completion_rate > 0
    print("  -> Contractor scorecard tests PASSED.")


def test_work_order_acknowledgment():
    print("\n[2/5] Testing Contractor Work Order Acknowledgment (ASSIGNED -> IN_PROGRESS)...")
    incident = db.get_incident("INC-2026-8812")
    assert incident is not None
    assert incident.status == IncidentStatus.ASSIGNED

    # Contractor crew acknowledges work order
    updated = contractor_service.acknowledge_work_order(
        incident_id="INC-2026-8812",
        contractor_id="CTR-001",
        notes="Crew arrived on site with bitumen compaction roller."
    )

    print(f"  -> Updated Status: {updated.status.value}")
    assert updated.status == IncidentStatus.IN_PROGRESS
    assert any("bitumen compaction roller" in a.notes for a in updated.audit_trail if a.notes)
    print("  -> Work order acknowledgment tests PASSED.")


def test_repair_evidence_submission():
    print("\n[3/5] Testing Completed Repair Evidence Submission & EXIF Telemetry Capture...")
    incident = db.get_incident("INC-2026-8812")
    assert incident is not None
    assert incident.status == IncidentStatus.IN_PROGRESS

    # 1. Create a synthetic repair "after" image
    test_img = np.full((480, 640, 3), 75, dtype=np.uint8)  # smooth dark asphalt
    cv2.putText(test_img, "SEALED ASPHALT REPAIR", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    _, encoded = cv2.imencode(".jpg", test_img)
    img_bytes = encoded.tobytes()

    upload_file = UploadFile(
        file=io.BytesIO(img_bytes),
        filename="completed_pothole_repair.jpg",
        headers={"content-type": "image/jpeg"}
    )

    # 2. Submit repair evidence
    res = contractor_service.process_repair_submission(
        incident_id="INC-2026-8812",
        contractor_id="CTR-001",
        file=upload_file,
        latitude=18.520420,
        longitude=73.856710,
        accuracy_m=4.2,
        asphalt_mix_type="Hot-Mix Asphalt (HMA)",
        asphalt_used_kg=110.0,
        engineering_notes="Cold-milled defect cavity, applied tack coat, compacted 110kg hot-mix bitumen."
    )

    print(f"  -> Submission ID: {res.submission.id}")
    print(f"  -> Incident Transition: {res.previous_status.value} -> {res.new_status.value}")
    print(f"  -> Photo Stored URL: {res.submission.repair_photo_url}")
    print(f"  -> Telemetry: ({res.submission.submission_latitude}, {res.submission.submission_longitude})")

    assert res.submission.id.startswith("SUB-2026-")
    assert res.new_status in [IncidentStatus.VERIFICATION_PENDING, IncidentStatus.VERIFIED]
    assert res.submission.asphalt_used_kg == 110.0

    # 3. Verify on-disk storage
    saved_filename = Path(res.submission.repair_photo_url).name
    saved_disk_path = REPAIRS_DIR / saved_filename
    assert saved_disk_path.exists(), f"Saved repair photo not found at {saved_disk_path}"

    # 4. Verify database persistence
    stored_sub = db.get_repair_submission(res.submission.id)
    assert stored_sub is not None
    assert stored_sub.id == res.submission.id

    print("  -> Repair evidence submission tests PASSED.")


def test_authorization_and_validation_guards():
    print("\n[4/5] Testing Authorization & Lifecycle State Machine Guards...")
    # Incident INC-2026-8812 is assigned to CTR-001 and currently in VERIFICATION_PENDING

    # Subtest 4A: Unauthorized contractor submission (CTR-002 trying to submit for CTR-001)
    test_img = np.full((100, 100, 3), 50, dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", test_img)

    try:
        contractor_service.process_repair_submission(
            incident_id="INC-2026-8812",
            contractor_id="CTR-002",  # UNAUTHORIZED!
            file=UploadFile(file=io.BytesIO(encoded.tobytes()), filename="fake.jpg"),
            latitude=18.5204,
            longitude=73.8567
        )
        assert False, "Failed to reject unauthorized contractor submission"
    except HTTPException as e:
        print(f"  -> Unauthorized contractor correctly rejected: HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 403

    # Subtest 4B: Attempting to submit for an incident already in VERIFICATION_PENDING
    try:
        contractor_service.process_repair_submission(
            incident_id="INC-2026-8812",
            contractor_id="CTR-001",
            file=UploadFile(file=io.BytesIO(encoded.tobytes()), filename="repeat.jpg"),
            latitude=18.5204,
            longitude=73.8567
        )
        assert False, "Failed to reject submission for incident already in VERIFICATION_PENDING"
    except HTTPException as e:
        print(f"  -> Ineligible lifecycle state correctly rejected: HTTP {e.status_code} ({e.detail})")
        assert e.status_code == 400

    # Subtest 4C: Non-existent incident
    try:
        contractor_service.process_repair_submission(
            incident_id="INC-DOES-NOT-EXIST",
            contractor_id="CTR-001",
            file=UploadFile(file=io.BytesIO(encoded.tobytes()), filename="fake.jpg"),
            latitude=18.5204,
            longitude=73.8567
        )
        assert False, "Failed to reject non-existent incident"
    except HTTPException as e:
        print(f"  -> Non-existent incident correctly rejected: HTTP {e.status_code}")
        assert e.status_code == 404

    print("  -> Authorization and validation guard tests PASSED.")


def test_contractor_queue_and_submissions_list():
    print("\n[5/5] Testing Contractor Queue & Submission Listing...")
    # List queue for CTR-001
    queue = db.list_incidents(contractor_id="CTR-001")
    assert len(queue) >= 1
    print(f"  -> CTR-001 Active Queue Length: {len(queue)}")

    # List submissions for CTR-001
    submissions = db.list_repair_submissions(contractor_id="CTR-001")
    assert len(submissions) >= 1
    print(f"  -> CTR-001 Recorded Submissions: {len(submissions)}")
    assert submissions[0].contractor_id == "CTR-001"

    print("  -> Contractor queue and submission listing tests PASSED.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("==========================================================")
    print(" [TEST] RUNNING PHASE 4 TEST SUITE: RoadSentinel AI")
    print("==========================================================")
    test_contractor_scorecard()
    test_work_order_acknowledgment()
    test_repair_evidence_submission()
    test_authorization_and_validation_guards()
    test_contractor_queue_and_submissions_list()
    print("\n[SUCCESS] ALL PHASE 4 TESTS COMPLETED WITH 100% SUCCESS!")

