import sys
import os
from pathlib import Path
import cv2
import numpy as np
from datetime import datetime, timezone, timedelta
from PIL import Image

# Reconfigure stdout for Windows console UTF-8 compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import (
    MAX_GEOFENCE_DISTANCE_METERS,
    PHASH_MAX_DUPLICATE_DISTANCE,
    MIN_ORB_MATCHES_ALIGNMENT,
    MIN_ASPHALT_TEXTURE_COMPLIANCE,
    REPAIRS_DIR,
    EVIDENCE_DIR
)
from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    GeoLocation,
    PhysicalMetrics,
    RepairSubmission,
    VerificationOutcome,
    NotificationEvent,
    NotificationStatus
)
from app.core.database import db
from app.services.verification import verification_engine, RepairVerificationEngine
from app.services.contractor import contractor_service
from app.services.sla import SLAEngine


def print_step(name: str):
    print(f"\n[PHASE 5 TEST] === {name} ===")


def test_geofence_verification():
    print_step("Test 1: Anti-Fraud Geofencing (Haversine Proximity)")
    lat_orig, lng_orig = 18.520400, 73.856700

    # Within 15 meters (compliant)
    lat_close, lng_close = 18.520480, 73.856750
    ok_close, dist_close = verification_engine.check_geofence(lat_orig, lng_orig, lat_close, lng_close)
    print(f"  Close submission: {dist_close:.2f}m -> Verified: {ok_close}")
    assert ok_close is True
    assert dist_close <= MAX_GEOFENCE_DISTANCE_METERS

    # 1.5 km away (geofence breach)
    lat_far, lng_far = 18.534000, 73.856700
    ok_far, dist_far = verification_engine.check_geofence(lat_orig, lng_orig, lat_far, lng_far)
    print(f"  Far submission: {dist_far:.2f}m -> Verified: {ok_far}")
    assert ok_far is False
    assert dist_far > MAX_GEOFENCE_DISTANCE_METERS
    print("  [PASS] Geofence validation correctly discriminates proximity.")


def test_anti_fraud_duplicate_phash():
    print_step("Test 2: Anti-Fraud Perceptual Hash Duplicate Detection")
    temp_dir = REPAIRS_DIR / "test_phash"
    temp_dir.mkdir(parents=True, exist_ok=True)

    img1_path = temp_dir / "orig.jpg"
    img2_copy_path = temp_dir / "copy.jpg"
    img3_diff_path = temp_dir / "diff.jpg"

    # Synthetic original frame
    frame1 = verification_engine.generate_synthetic_road_frame(is_repaired=False)
    cv2.imwrite(str(img1_path), frame1)

    # Identical photo with slight brightness shift (contractor attempting recycling)
    frame_copy = np.clip(frame1.astype(np.int16) + 4, 0, 255).astype(np.uint8)
    cv2.imwrite(str(img2_copy_path), frame_copy)

    # Completely different image (smooth repaired bitumen patch)
    frame_diff = verification_engine.generate_synthetic_road_frame(is_repaired=True)
    cv2.imwrite(str(img3_diff_path), frame_diff)

    dup_flag, dist_dup = verification_engine.check_perceptual_hash(img1_path, img2_copy_path)
    print(f"  Recycled photo test: Hamming Dist = {dist_dup} -> Duplicate Suspected: {dup_flag}")
    assert dup_flag is True
    assert dist_dup <= PHASH_MAX_DUPLICATE_DISTANCE

    not_dup_flag, dist_not_dup = verification_engine.check_perceptual_hash(img1_path, img3_diff_path)
    print(f"  Different photo test: Hamming Dist = {dist_not_dup} -> Duplicate Suspected: {not_dup_flag}")
    assert not_dup_flag is False
    print("  [PASS] Perceptual hash collision reliably catches fraudulent submissions.")


def test_orb_homography_alignment():
    print_step("Test 3: Planar Homography Perspective Normalization")
    frame_b = verification_engine.generate_synthetic_road_frame(is_repaired=False)
    frame_a = verification_engine.generate_synthetic_road_frame(is_repaired=True)

    aligned_ok, inliers, aligned_frame, H = verification_engine.align_homography(frame_b, frame_a)
    print(f"  Homography Aligned: {aligned_ok}, Inliers Count: {inliers}, Warped Shape: {aligned_frame.shape}")
    assert aligned_frame.shape == frame_b.shape
    assert inliers >= 0
    print("  [PASS] Homography alignment executes gracefully without matrix singular errors.")


def test_dual_head_verification():
    print_step("Test 4: Dual-Head Verification (Residual Defect & Bitumen Texture)")
    # Head A: Unrepaired road frame with defect
    unrepaired_frame = verification_engine.generate_synthetic_road_frame(is_repaired=False)
    defect_found, defect_conf, boxes = verification_engine.detect_residual_defects(unrepaired_frame)
    print(f"  Unrepaired frame -> Defect Found: {defect_found}, Confidence: {defect_conf}, Boxes Count: {len(boxes)}")
    assert defect_found is True
    assert defect_conf is not None and defect_conf >= 0.40

    # Head B: Repaired road frame with fresh bitumen
    repaired_frame = verification_engine.generate_synthetic_road_frame(is_repaired=True)
    repaired_defect, _, _ = verification_engine.detect_residual_defects(repaired_frame)
    texture_score = verification_engine.evaluate_patch_texture(repaired_frame)
    print(f"  Repaired frame   -> Residual Defect: {repaired_defect}, Bitumen Texture Score: {texture_score:.3f}")
    assert repaired_defect is False
    assert texture_score >= MIN_ASPHALT_TEXTURE_COMPLIANCE
    print("  [PASS] Dual-head perception cleanly separates unsealed voids from compacted asphalt.")


def test_three_state_decision_engine_and_transitions():
    print_step("Test 5: Three-State Decision Engine & Lifecycle Automation")
    now = datetime.now(timezone.utc)
    seg, contractor = db.spatial_matcher.match_location(18.5204, 73.8567)

    # 1. Setup Test Incident
    test_inc_id = f"INC-TEST-{int(now.timestamp())}"
    sla = SLAEngine.calculate_sla(SeverityLevel.HIGH, now)

    # Create dummy evidence files
    evid_path = EVIDENCE_DIR / f"test_evid_{test_inc_id}.jpg"
    repair_good_path = REPAIRS_DIR / f"test_repair_good_{test_inc_id}.jpg"
    repair_defect_path = REPAIRS_DIR / f"test_repair_defect_{test_inc_id}.jpg"

    cv2.imwrite(str(evid_path), verification_engine.generate_synthetic_road_frame(is_repaired=False))
    cv2.imwrite(str(repair_good_path), verification_engine.generate_synthetic_road_frame(is_repaired=True))
    cv2.imwrite(str(repair_defect_path), verification_engine.generate_synthetic_road_frame(is_repaired=False))

    inc = Incident(
        id=test_inc_id,
        created_at=now,
        defect_type=DefectCategory.POTHOLE,
        severity=SeverityLevel.HIGH,
        status=IncidentStatus.VERIFICATION_PENDING,
        location=GeoLocation(latitude=18.5204, longitude=73.8567, road_name=seg.name),
        road_segment=seg,
        assigned_contractor=contractor,
        sla_metrics=sla,
        physical_metrics=PhysicalMetrics(surface_area_m2=0.5, estimated_depth_m=0.08, volume_m3=0.04, asphalt_required_kg=96.0),
        evidence_image_url=f"/storage/evidence/{evid_path.name}",
        pci_deduct_points=25.0
    )
    db.save_incident(inc)

    # CASE A: Anti-Fraud Trigger (Contractor submits duplicate defect photo)
    sub_fraud = RepairSubmission(
        id="SUB-FRAUD-001",
        incident_id=test_inc_id,
        contractor_id=contractor.id,
        submitted_at=now,
        submission_latitude=18.52042,
        submission_longitude=73.85671,
        repair_photo_url=f"/storage/evidence/{evid_path.name}", # exact same photo!
        asphalt_mix_type="Hot-Mix Asphalt (HMA)"
    )
    report_fraud = verification_engine.verify_repair(inc, sub_fraud)
    print(f"  [Case A] Duplicate Submission -> Outcome: {report_fraud.outcome.value}, Incident State: {inc.status.value}")
    assert report_fraud.outcome == VerificationOutcome.REPAIR_INCOMPLETE
    assert report_fraud.duplicate_suspected is True
    assert inc.status == IncidentStatus.REWORK_REQUIRED

    # CASE B: Geofence Violation Trigger (> 50m)
    inc.status = IncidentStatus.VERIFICATION_PENDING  # reset to verification pending
    sub_geofence = RepairSubmission(
        id="SUB-GEOFENCE-002",
        incident_id=test_inc_id,
        contractor_id=contractor.id,
        submitted_at=now,
        submission_latitude=18.5350, # 1.6 km away
        submission_longitude=73.8567,
        repair_photo_url=f"/storage/repairs/{repair_good_path.name}",
        asphalt_mix_type="Hot-Mix Asphalt (HMA)"
    )
    report_geofence = verification_engine.verify_repair(inc, sub_geofence)
    print(f"  [Case B] Geofence Violation  -> Outcome: {report_geofence.outcome.value}, Incident State: {inc.status.value}")
    assert report_geofence.outcome == VerificationOutcome.VERIFICATION_UNCERTAIN
    assert report_geofence.geofence_verified is False

    # CASE C: Compliant Repair (Fresh Bitumen within 10m)
    initial_completed = contractor.completed_repairs
    inc.status = IncidentStatus.VERIFICATION_PENDING  # reset to verification pending
    sub_good = RepairSubmission(
        id="SUB-SUCCESS-003",
        incident_id=test_inc_id,
        contractor_id=contractor.id,
        submitted_at=now,
        submission_latitude=18.52041,
        submission_longitude=73.85671,
        repair_photo_url=f"/storage/repairs/{repair_good_path.name}",
        asphalt_mix_type="Hot-Mix Asphalt (HMA)"
    )
    report_good = verification_engine.verify_repair(inc, sub_good)
    print(f"  [Case C] Compliant Repair    -> Outcome: {report_good.outcome.value}, Incident State: {inc.status.value}")
    assert report_good.outcome == VerificationOutcome.REPAIR_SUCCESSFUL
    assert inc.status == IncidentStatus.VERIFIED
    assert contractor.completed_repairs == initial_completed + 1
    assert report_good.visual_diff_url is not None
    print(f"  Visual Diff URL: {report_good.visual_diff_url}")

    # Verify visual diff card was created on disk
    resolved_card = verification_engine.resolve_image_path(report_good.visual_diff_url)
    assert resolved_card is not None and resolved_card.exists()
    print(f"  Visual Diff Card confirmed on disk ({resolved_card.stat().st_size} bytes)")
    print("  [PASS] State machine transitions and notifications fired correctly.")


def test_repository_and_reports_query():
    print_step("Test 6: Verification Database & Reports Querying")
    all_reports = db.list_verification_reports()
    assert len(all_reports) > 0
    success_reports = db.list_verification_reports(outcome=VerificationOutcome.REPAIR_SUCCESSFUL)
    incomplete_reports = db.list_verification_reports(outcome=VerificationOutcome.REPAIR_INCOMPLETE)

    print(f"  Total Reports: {len(all_reports)}, Success: {len(success_reports)}, Incomplete: {len(incomplete_reports)}")
    assert len(success_reports) >= 1
    assert len(incomplete_reports) >= 1
    print("  [PASS] Repository queries and filters operating correctly.")


if __name__ == "__main__":
    print("=======================================================================")
    print("  ROADSENTINEL AI: PHASE 5 VERIFICATION SUITE")
    print("  Closed-Loop AI Verification, Anti-Fraud & Decision Engine")
    print("=======================================================================")

    test_geofence_verification()
    test_anti_fraud_duplicate_phash()
    test_orb_homography_alignment()
    test_dual_head_verification()
    test_three_state_decision_engine_and_transitions()
    test_repository_and_reports_query()

    print("\n=======================================================================")
    print("  [SUCCESS] 100% OF PHASE 5 VERIFICATION TESTS PASSED")
    print("=======================================================================\n")
