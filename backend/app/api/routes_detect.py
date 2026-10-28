import shutil
import uuid
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List

from app.core.config import UPLOAD_DIR, EVIDENCE_DIR
from app.models.schemas import (
    VideoProcessingSummary,
    TrackedDefect,
    BoundingBox,
    PhysicalMetrics,
    GeoLocation,
    SeverityLevel
)
from app.services.detector import RoadPerceptionEngine
from app.services.tracker import ByteTrackDefectTracker
from app.services.telemetry import TelemetrySynchronizer
from app.services.quantifier import DistressQuantifier

router = APIRouter(prefix="/detect", tags=["Phase 1: Perception & Telemetry Engine"])
detector = RoadPerceptionEngine()


@router.post("/video", response_model=VideoProcessingSummary)
async def process_video_stream(
    video_file: UploadFile = File(...),
    gpx_file: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(18.5204),
    longitude: Optional[float] = Form(73.8567),
    road_name: Optional[str] = Form("State Highway 17 North"),
    sample_interval: Optional[int] = Form(4)
):
    """
    Ingests road patrol video + optional GPX telemetry track.
    Executes YOLOv8 detection, ByteTrack deduplication, and asphalt volumetric estimation.
    """
    # 1. Save uploaded video
    vid_ext = Path(video_file.filename).suffix or ".mp4"
    temp_vid_name = f"patrol_{uuid.uuid4().hex[:8]}{vid_ext}"
    temp_vid_path = UPLOAD_DIR / temp_vid_name

    with open(temp_vid_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # 2. Save GPX if provided
    gpx_path_str = None
    if gpx_file and gpx_file.filename:
        temp_gpx_name = f"telemetry_{uuid.uuid4().hex[:8]}.gpx"
        temp_gpx_path = UPLOAD_DIR / temp_gpx_name
        with open(temp_gpx_path, "wb") as buffer:
            shutil.copyfileobj(gpx_file.file, buffer)
        gpx_path_str = str(temp_gpx_path)

    # 3. Initialize Telemetry Synchronizer
    telemetry_sync = TelemetrySynchronizer(gpx_path=gpx_path_str)

    # 4. Open video capture
    cap = cv2.VideoCapture(str(temp_vid_path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Unable to decode uploaded video stream.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    duration = total_frames / fps

    tracker = ByteTrackDefectTracker()
    frame_idx = 0
    sampled_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0:
            timestamp_sec = frame_idx / fps
            detections = detector.detect_frame(frame)
            tracker.update(detections, frame, frame_idx, timestamp_sec)
            sampled_count += 1

        frame_idx += 1

    cap.release()

    # 5. Finalize deduplicated defect tracks
    finalized_defects = tracker.finalize_tracks(
        telemetry_sync=telemetry_sync,
        video_duration=duration,
        road_name=road_name
    )

    return VideoProcessingSummary(
        video_filename=video_file.filename,
        total_frames_analyzed=sampled_count,
        video_fps=round(fps, 1),
        duration_seconds=round(duration, 2),
        unique_defects_count=len(finalized_defects),
        defects=finalized_defects
    )


@router.post("/image", response_model=List[TrackedDefect])
async def process_single_image(
    image_file: UploadFile = File(...),
    latitude: Optional[float] = Form(18.5204),
    longitude: Optional[float] = Form(73.8567),
    road_name: Optional[str] = Form("Surveyed Point")
):
    """
    Direct single-frame inspection and instant material volume quantification.
    """
    contents = await image_file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image file format.")

    h, w = frame.shape[:2]
    detections = detector.detect_frame(frame)
    results = []

    for idx, det in enumerate(detections):
        box_w = det.x2 - det.x1
        box_h = det.y2 - det.y1
        area_ratio = (box_w * box_h) / (w * h)

        severity = SeverityLevel.HIGH if area_ratio > 0.08 else (SeverityLevel.MEDIUM if area_ratio > 0.03 else SeverityLevel.LOW)
        metrics = DistressQuantifier.calculate_metrics(box_w, box_h, severity)

        # Save annotated image
        annotated = frame.copy()
        cv2.rectangle(annotated, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), (0, 0, 255), 3)
        label = f"{det.category.value.upper()} [{severity.value}] {det.confidence:.2f}"
        cv2.putText(annotated, label, (int(det.x1), max(int(det.y1) - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        filename = f"img_defect_{uuid.uuid4().hex[:6]}.jpg"
        cv2.imwrite(str(EVIDENCE_DIR / filename), annotated)

        results.append(TrackedDefect(
            track_id=idx + 1,
            category=det.category,
            severity=severity,
            confidence=det.confidence,
            location=GeoLocation(latitude=latitude, longitude=longitude, road_name=road_name),
            physical_metrics=metrics,
            best_frame_evidence=f"/storage/evidence/{filename}",
            timestamp_sec=0.0,
            frame_number=0
        ))

    return results

