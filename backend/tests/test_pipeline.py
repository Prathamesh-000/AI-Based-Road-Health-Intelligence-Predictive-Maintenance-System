import sys
import os
from pathlib import Path
import cv2
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.detector import RoadPerceptionEngine, DefectTracker
from app.services.verification import RepairVerificationEngine
from app.services.spatial import SpatialAssignmentService
from app.models.schemas import GeoCoordinates, DefectCategory, SeverityLevel


def run_tests():
    print("[1/3] Testing RoadPerceptionEngine...")
    engine = RoadPerceptionEngine()

    # Generate synthetic road image with pothole
    test_img = np.full((480, 640, 3), 110, dtype=np.uint8)
    # Add road texture
    noise = np.random.normal(0, 8, test_img.shape).astype(np.uint8)
    test_img = cv2.add(test_img, noise)
    # Draw dark pothole in bottom road ROI
    cv2.circle(test_img, (320, 360), 45, (25, 25, 25), -1)
    cv2.ellipse(test_img, (320, 360), (55, 35), 15, 0, 360, (20, 20, 20), -1)

    boxes = engine.detect_frame(test_img)
    print(f"  -> Detected {len(boxes)} defect bounding boxes.")
    assert len(boxes) > 0, "Failed to detect synthetic pothole"
    print(f"  -> Box 0 category: {boxes[0].category}, confidence: {boxes[0].confidence}")

    print("\n[2/3] Testing SpatialAssignmentService...")
    spatial = SpatialAssignmentService()
    contractor, road = spatial.match_contractor_for_location(18.5204, 73.8567)
    print(f"  -> Matched contractor: {contractor.name} ({contractor.id}) for '{road}'")
    assert contractor is not None

    print("\n[3/3] Testing RepairVerificationEngine...")
    verifier = RepairVerificationEngine(detector=engine)

    # Save test before image
    before_path = backend_dir / "storage" / "evidence" / "test_before.jpg"
    before_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(before_path), test_img)

    # Create repaired "after" image (sealed with fresh asphalt patch)
    after_img = test_img.copy()
    # Fill pothole with smooth dark asphalt
    cv2.circle(after_img, (320, 360), 55, (60, 60, 60), -1)
    after_path = backend_dir / "storage" / "repairs" / "test_after.jpg"
    after_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(after_path), after_img)

    coords = GeoCoordinates(latitude=18.5204, longitude=73.8567)
    report = verifier.verify_repair(
        incident_id="TEST-001",
        img_before_path=str(before_path),
        img_after_path=str(after_path),
        incident_coords=coords,
        submission_coords=(18.5204, 73.8567)
    )

    print(f"  -> Verification Outcome: {report.outcome}")
    print(f"  -> Confidence: {report.confidence_score * 100:.1f}%")
    print(f"  -> Homography Matches: {report.feature_matches_count}")
    print(f"  -> Explanation: {report.explanation}")
    assert report.outcome is not None

    print("\n✅ ALL ENGINE PIPELINE TESTS PASSED!")


if __name__ == "__main__":
    run_tests()
