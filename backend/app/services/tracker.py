import cv2
import numpy as np
import time
from typing import List, Dict, Tuple
from pathlib import Path

from app.core.config import (
    IOU_TRACKING_THRESHOLD,
    MAX_TRACK_AGE,
    MIN_TRACK_HITS,
    MIN_SEVERITY_AREA_RATIO_HIGH,
    MIN_SEVERITY_AREA_RATIO_MED,
    EVIDENCE_DIR
)
from app.models.schemas import (
    BoundingBox,
    TrackedDefect,
    SeverityLevel,
    GeoLocation
)
from app.services.quantifier import DistressQuantifier
from app.services.telemetry import TelemetrySynchronizer


class ByteTrackDefectTracker:
    """
    Multi-Object Tracking (MOT) & deduplication engine using IoU distance matrices
    and Laplacian sharpness evaluation (ByteTrack/SORT paradigm).
    """
    def __init__(
        self,
        iou_thresh: float = IOU_TRACKING_THRESHOLD,
        max_age: int = MAX_TRACK_AGE,
        min_hits: int = MIN_TRACK_HITS
    ):
        self.iou_thresh = iou_thresh
        self.max_age = max_age
        self.min_hits = min_hits
        self.next_track_id = 1
        self.active_tracks: Dict[int, Dict] = {}

    def _compute_iou(self, boxA: Tuple[float, float, float, float], boxB: Tuple[float, float, float, float]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        union = float(boxAArea + boxBArea - interArea)
        return interArea / union if union > 0 else 0.0

    def update(
        self,
        detections: List[BoundingBox],
        frame: np.ndarray,
        frame_idx: int,
        timestamp_sec: float
    ):
        assigned_det_indices = set()

        # Compute sharpness of incoming frame using Laplacian variance
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 1. Associate with active tracks
        for track_id, track in list(self.active_tracks.items()):
            best_iou = 0.0
            best_idx = -1

            for idx, det in enumerate(detections):
                if idx in assigned_det_indices:
                    continue
                iou = self._compute_iou(track["last_box"], (det.x1, det.y1, det.x2, det.y2))
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_iou >= self.iou_thresh and best_idx >= 0:
                det = detections[best_idx]
                track["last_box"] = (det.x1, det.y1, det.x2, det.y2)
                track["hits"] += 1
                track["age"] = 0
                assigned_det_indices.add(best_idx)

                # Update best frame if current detection is sharper and higher confidence
                quality_metric = det.confidence * frame_sharpness
                if quality_metric > track["best_metric"]:
                    track["best_metric"] = quality_metric
                    track["best_box"] = det
                    track["best_frame"] = frame.copy()
                    track["best_frame_idx"] = frame_idx
                    track["best_timestamp"] = timestamp_sec
            else:
                track["age"] += 1

        # 2. Initialize new tracks for unassociated detections
        for idx, det in enumerate(detections):
            if idx not in assigned_det_indices:
                track_id = self.next_track_id
                self.next_track_id += 1

                self.active_tracks[track_id] = {
                    "track_id": track_id,
                    "last_box": (det.x1, det.y1, det.x2, det.y2),
                    "best_box": det,
                    "best_frame": frame.copy(),
                    "best_frame_idx": frame_idx,
                    "best_timestamp": timestamp_sec,
                    "best_metric": det.confidence * frame_sharpness,
                    "hits": 1,
                    "age": 0,
                    "category": det.category
                }

    def finalize_tracks(
        self,
        telemetry_sync: TelemetrySynchronizer,
        video_duration: float,
        road_name: str = "Patrol Sector"
    ) -> List[TrackedDefect]:
        """
        Deduplicates tracks, computes physical metrics, fetches spatial GPS,
        saves evidence crops, and returns final defect records.
        """
        finalized_defects: List[TrackedDefect] = []

        for track_id, track in self.active_tracks.items():
            if track["hits"] < self.min_hits:
                continue

            det: BoundingBox = track["best_box"]
            frame = track["best_frame"]
            h, w = frame.shape[:2]

            box_w = det.x2 - det.x1
            box_h = det.y2 - det.y1
            area_ratio = (box_w * box_h) / (w * h)

            # Determine distress severity
            if area_ratio >= MIN_SEVERITY_AREA_RATIO_HIGH:
                severity = SeverityLevel.HIGH
            elif area_ratio >= MIN_SEVERITY_AREA_RATIO_MED:
                severity = SeverityLevel.MEDIUM
            else:
                severity = SeverityLevel.LOW

            # Physical asphalt & volume math
            physical_metrics = DistressQuantifier.calculate_metrics(box_w, box_h, severity)

            # Synchronize GPS coordinate
            coords = telemetry_sync.get_coordinate_at_time(
                elapsed_seconds=track["best_timestamp"],
                total_duration=video_duration,
                road_name=road_name
            )

            # Annotate and save best evidence crop
            annotated_frame = frame.copy()
            pt1 = (int(det.x1), int(det.y1))
            pt2 = (int(det.x2), int(det.y2))
            cv2.rectangle(annotated_frame, pt1, pt2, (0, 0, 255), 3)

            label = f"ID:{track_id} {det.category.value.upper()} [{severity.value}] {det.confidence:.2f}"
            cv2.putText(
                annotated_frame, label, (pt1[0], max(pt1[1] - 8, 25)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
            )

            evidence_filename = f"defect_tr{track_id}_{int(time.time())}.jpg"
            save_path = EVIDENCE_DIR / evidence_filename
            cv2.imwrite(str(save_path), annotated_frame)

            finalized_defects.append(TrackedDefect(
                track_id=track_id,
                category=det.category,
                severity=severity,
                confidence=round(det.confidence, 3),
                location=coords,
                physical_metrics=physical_metrics,
                best_frame_evidence=f"/storage/evidence/{evidence_filename}",
                timestamp_sec=round(track["best_timestamp"], 2),
                frame_number=track["best_frame_idx"]
            ))

        return finalized_defects

