import sys
import os
from pathlib import Path
import cv2
import numpy as np

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.telemetry import TelemetrySynchronizer
from app.services.quantifier import DistressQuantifier
from app.services.detector import RoadPerceptionEngine
from app.services.tracker import ByteTrackDefectTracker
from app.models.schemas import SeverityLevel, DefectCategory, BoundingBox


def test_telemetry_gpx():
    print("[1/4] Testing Telemetry Synchronizer & GPX Parsing...")
    # 1. Create a synthetic GPX file
    gpx_content = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="RoadSentinelTest" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Patrol Route Sector 4</name>
    <trkseg>
      <trkpt lat="18.520000" lon="73.850000">
        <ele>560.0</ele>
        <time>2026-10-28T10:00:00Z</time>
      </trkpt>
      <trkpt lat="18.530000" lon="73.860000">
        <ele>565.0</ele>
        <time>2026-10-28T10:00:10Z</time>
      </trkpt>
      <trkpt lat="18.540000" lon="73.870000">
        <ele>570.0</ele>
        <time>2026-10-28T10:00:20Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""
    test_gpx_path = backend_dir / "storage" / "uploads" / "test_route.gpx"
    test_gpx_path.parent.mkdir(parents=True, exist_ok=True)
    with open(test_gpx_path, "w", encoding="utf-8") as f:
        f.write(gpx_content)

    sync = TelemetrySynchronizer(str(test_gpx_path))
    assert len(sync.points) == 3, f"Expected 3 GPX points, got {len(sync.points)}"

    # Test midpoint interpolation at 10 seconds of a 20-second video
    midpoint_coord = sync.get_coordinate_at_time(elapsed_seconds=10.0, total_duration=20.0)
    print(f"  -> Midpoint (10s) GPS: Lat {midpoint_coord.latitude}, Lng {midpoint_coord.longitude}, Elevation: {midpoint_coord.elevation_m}m")
    assert abs(midpoint_coord.latitude - 18.530000) < 0.0001, "GPX midpoint latitude interpolation failed"
    print("  -> Telemetry GPX test PASSED.")


def test_distress_quantifier():
    print("\n[2/4] Testing Volumetric & Asphalt Material Solver...")
    metrics = DistressQuantifier.calculate_metrics(
        box_width_px=200.0,
        box_height_px=150.0,
        severity=SeverityLevel.HIGH
    )
    print(f"  -> Ground Surface Area: {metrics.surface_area_m2} m²")
    print(f"  -> Estimated Depth: {metrics.estimated_depth_m} m")
    print(f"  -> Volume: {metrics.volume_m3} m³")
    print(f"  -> Hot-Mix Asphalt Required: {metrics.asphalt_required_kg} kg")

    assert metrics.surface_area_m2 > 0, "Surface area calculation error"
    assert metrics.volume_m3 > 0, "Volume calculation error"
    assert metrics.asphalt_required_kg == round(metrics.volume_m3 * 2400.0, 2), "Asphalt mass formula error"
    print("  -> Volumetric solver test PASSED.")


def test_detector_engine():
    print("\n[3/4] Testing RoadPerceptionEngine...")
    engine = RoadPerceptionEngine()

    # Generate synthetic road frame with dark pothole depression
    frame = np.full((480, 640, 3), 110, dtype=np.uint8)
    noise = np.random.normal(0, 8, frame.shape).astype(np.uint8)
    frame = cv2.add(frame, noise)
    cv2.circle(frame, (320, 360), 45, (25, 25, 25), -1)

    boxes = engine.detect_frame(frame)
    print(f"  -> Detected {len(boxes)} road distress bounding boxes.")
    assert len(boxes) > 0, "Failed to detect road defect"
    print(f"  -> Defect: {boxes[0].category.value}, Confidence: {boxes[0].confidence:.2f}")
    print("  -> Perception detector test PASSED.")


def test_bytetrack_deduplication():
    print("\n[4/4] Testing ByteTrack Deduplication Across Consecutive Frames...")
    tracker = ByteTrackDefectTracker()

    # Simulate vehicle driving past ONE pothole across 25 consecutive frames
    for i in range(25):
        # Defect moves slightly across consecutive frames as car moves forward
        x1 = 280.0 + (i * 1.5)
        y1 = 300.0 + (i * 2.5)
        x2 = x1 + 80.0
        y2 = y1 + 60.0

        det = BoundingBox(
            x1=x1, y1=y1, x2=x2, y2=y2,
            confidence=0.85 + (i * 0.003),
            category=DefectCategory.POTHOLE
        )

        dummy_frame = np.full((480, 640, 3), 100, dtype=np.uint8)
        cv2.circle(dummy_frame, (int(x1 + 40), int(y1 + 30)), 25, (20, 20, 20), -1)

        tracker.update(
            detections=[det],
            frame=dummy_frame,
            frame_idx=i,
            timestamp_sec=i / 30.0
        )

    # Finalize tracks
    sync = TelemetrySynchronizer()
    defects = tracker.finalize_tracks(sync, video_duration=1.0)

    print(f"  -> Total input frames processed: 25")
    print(f"  -> Deduplicated unique defects output: {len(defects)}")

    # CRITICAL CHECK: 25 frames of the same moving pothole MUST produce exactly 1 ticket!
    assert len(defects) == 1, f"Deduplication failed! Expected 1 defect, but got {len(defects)}"
    defect = defects[0]
    print(f"  -> Track ID: {defect.track_id}")
    print(f"  -> Optimal Frame: #{defect.frame_number} at {defect.timestamp_sec}s")
    print(f"  -> Asphalt Material Required: {defect.physical_metrics.asphalt_required_kg} kg")
    print(f"  -> GPS Location: {defect.location.latitude}, {defect.location.longitude}")
    print("  -> ByteTrack deduplication test PASSED.")


if __name__ == "__main__":
    print("==========================================================")
    print(" 🧪 RUNNING PHASE 1 TEST SUITE: RoadSentinel AI")
    print("==========================================================")
    test_telemetry_gpx()
    test_distress_quantifier()
    test_detector_engine()
    test_bytetrack_deduplication()
    print("\n🎉 ALL PHASE 1 COMPONENT TESTS PASSED WITH 100% SUCCESS!")

