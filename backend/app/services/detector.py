import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import time

from app.config import (
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    MIN_SEVERITY_AREA_RATIO_HIGH,
    MIN_SEVERITY_AREA_RATIO_MED,
    EVIDENCE_DIR
)
from app.models.schemas import (
    DefectCategory,
    SeverityLevel,
    BoundingBox,
    TrackedDefect
)

# Try importing ultralytics YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class DefectTracker:
    """
    Lightweight IoU & centroid-based object tracker to deduplicate road distress
    across video frames (ByteTrack/SORT paradigm).
    """
    def __init__(self, iou_thresh: float = 0.35, max_age: int = 15):
        self.iou_thresh = iou_thresh
        self.max_age = max_age
        self.next_id = 1
        self.tracks: Dict[int, Dict] = {}

    def _compute_iou(self, boxA: Tuple[float, float, float, float], boxB: Tuple[float, float, float, float]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        union = float(boxAArea + boxBArea - interArea)
        return interArea / union if union > 0 else 0.0

    def update(self, detections: List[BoundingBox], frame: np.ndarray, frame_idx: int, timestamp: float) -> List[int]:
        matched_track_ids = []
        assigned_det_indices = set()

        # Update existing tracks
        for track_id, track in list(self.tracks.items()):
            best_iou = 0.0
            best_det_idx = -1

            for idx, det in enumerate(detections):
                if idx in assigned_det_indices:
                    continue
                iou = self._compute_iou(track["last_box"], (det.x1, det.y1, det.x2, det.y2))
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = idx

            if best_iou >= self.iou_thresh and best_det_idx >= 0:
                det = detections[best_det_idx]
                track["last_box"] = (det.x1, det.y1, det.x2, det.y2)
                track["hits"] += 1
                track["age"] = 0
                assigned_det_indices.add(best_det_idx)
                matched_track_ids.append(track_id)

                # Compute frame sharpness (Laplacian variance)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

                if det.confidence * sharpness > track["best_metric"]:
                    track["best_metric"] = det.confidence * sharpness
                    track["best_box"] = det
                    track["best_frame"] = frame.copy()
                    track["best_frame_idx"] = frame_idx
                    track["best_timestamp"] = timestamp
            else:
                track["age"] += 1
                if track["age"] > self.max_age:
                    pass  # Keep in history for final extraction

        # Initialize new tracks for unassigned detections
        for idx, det in enumerate(detections):
            if idx not in assigned_det_indices:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

                track_id = self.next_id
                self.next_id += 1
                self.tracks[track_id] = {
                    "last_box": (det.x1, det.y1, det.x2, det.y2),
                    "best_box": det,
                    "best_frame": frame.copy(),
                    "best_frame_idx": frame_idx,
                    "best_timestamp": timestamp,
                    "best_metric": det.confidence * sharpness,
                    "hits": 1,
                    "age": 0,
                    "category": det.category
                }
                matched_track_ids.append(track_id)

        return matched_track_ids

    def get_finalized_defects(self, min_hits: int = 2) -> List[TrackedDefect]:
        results = []
        for track_id, track in self.tracks.items():
            if track["hits"] < min_hits:
                continue

            det: BoundingBox = track["best_box"]
            frame = track["best_frame"]
            h, w = frame.shape[:2]

            box_w = det.x2 - det.x1
            box_h = det.y2 - det.y1
            area_px = box_w * box_h
            area_ratio = area_px / (w * h)

            # Severity computation
            if area_ratio >= MIN_SEVERITY_AREA_RATIO_HIGH:
                severity = SeverityLevel.HIGH
                depth_m = 0.08  # ~8cm
            elif area_ratio >= MIN_SEVERITY_AREA_RATIO_MED:
                severity = SeverityLevel.MEDIUM
                depth_m = 0.05  # ~5cm
            else:
                severity = SeverityLevel.LOW
                depth_m = 0.03  # ~3cm

            # Physical estimations: 1 px ≈ 0.002 meters (at typical dashcam road focal distance)
            ground_area_m2 = (box_w * 0.002) * (box_h * 0.002)
            estimated_volume_m3 = round(ground_area_m2 * depth_m, 4)
            # Density of compacted hot-mix asphalt ≈ 2400 kg/m^3
            asphalt_kg = round(estimated_volume_m3 * 2400.0, 2)

            # Save annotated evidence crop/frame
            annotated_frame = frame.copy()
            p1 = (int(det.x1), int(det.y1))
            p2 = (int(det.x2), int(det.y2))
            cv2.rectangle(annotated_frame, p1, p2, (0, 0, 255), 3)
            label = f"{det.category.value.upper()} [{severity.value}] {det.confidence:.2f}"
            cv2.putText(annotated_frame, label, (p1[0], max(p1[1] - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            filename = f"defect_tr{track_id}_{int(time.time())}.jpg"
            save_path = EVIDENCE_DIR / filename
            cv2.imwrite(str(save_path), annotated_frame)

            results.append(TrackedDefect(
                track_id=track_id,
                category=det.category,
                severity=severity,
                confidence=round(det.confidence, 3),
                surface_area_px=round(area_px, 1),
                estimated_volume_m3=estimated_volume_m3,
                estimated_asphalt_kg=asphalt_kg,
                best_frame_path=f"/storage/evidence/{filename}",
                timestamp_sec=round(track["best_timestamp"], 2),
                frame_number=track["best_frame_idx"]
            ))

        return results


class RoadPerceptionEngine:
    """
    Core AI Perception Engine supporting YOLO deep learning inference with
    OpenCV computer vision fallback for road distress localization.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if YOLO_AVAILABLE:
            search_paths = [
                model_path,
                "yolov8n.pt",
                str(Path(__file__).resolve().parent.parent.parent / "yolov8n.pt"),
                str(Path(__file__).resolve().parent.parent / "yolov8n.pt")
            ]
            for p in search_paths:
                if p and Path(p).exists():
                    try:
                        self.model = YOLO(p)
                        print(f"[RoadPerceptionEngine] Loaded YOLO model from {p}")
                        break
                    except Exception:
                        pass

    def detect_frame(self, frame: np.ndarray) -> List[BoundingBox]:
        h, w = frame.shape[:2]
        boxes: List[BoundingBox] = []

        if self.model:
            try:
                results = self.model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
                for r in results:
                    for b in r.boxes:
                        coords = b.xyxy[0].cpu().numpy()
                        conf = float(b.conf[0].cpu().numpy())
                        cls_id = int(b.cls[0].cpu().numpy())
                        area_ratio = ((coords[2] - coords[0]) * (coords[3] - coords[1])) / (w * h)

                        boxes.append(BoundingBox(
                            x1=float(coords[0]),
                            y1=float(coords[1]),
                            x2=float(coords[2]),
                            y2=float(coords[3]),
                            confidence=conf,
                            category=DefectCategory.POTHOLE,
                            area_ratio=area_ratio
                        ))
                if boxes:
                    return boxes
            except Exception:
                pass

        # Robust Computer Vision Fallback (Depression & Edge Detection)
        roi_y_start = int(h * 0.35)
        roi = frame[roi_y_start:h, 0:w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Multi-scale Otsu + adaptive threshold
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10)
        combined = cv2.bitwise_or(otsu, adaptive)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        morph = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        morph = cv2.morphologyEx(morph, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (w * h * 0.003):  # Minimum defect area threshold
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect_ratio = bw / float(bh)
                if 0.3 < aspect_ratio < 4.5:
                    real_y1 = roi_y_start + by
                    real_y2 = real_y1 + bh
                    area_ratio = (bw * bh) / (w * h)

                    mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    mean_val = cv2.mean(gray, mask=mask)[0]
                    road_mean = cv2.mean(gray)[0]
                    contrast_diff = max(0, road_mean - mean_val)
                    conf = min(0.96, max(0.50, (contrast_diff / 40.0) + 0.5))

                    category = DefectCategory.POTHOLE
                    if aspect_ratio > 2.5:
                        category = DefectCategory.LONGITUDINAL_CRACK

                    boxes.append(BoundingBox(
                        x1=float(bx),
                        y1=float(real_y1),
                        x2=float(bx + bw),
                        y2=float(real_y2),
                        confidence=round(conf, 3),
                        category=category,
                        area_ratio=round(area_ratio, 4)
                    ))

        return boxes

    def process_video(self, video_path: str, sample_interval_frames: int = 5) -> List[TrackedDefect]:
        """
        Processes an input dashcam video stream, applying detection and tracking.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video stream: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        tracker = DefectTracker(iou_thresh=IOU_THRESHOLD)
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval_frames == 0:
                timestamp = frame_idx / fps
                detections = self.detect_frame(frame)
                tracker.update(detections, frame, frame_idx, timestamp)

            frame_idx += 1

        cap.release()
        return tracker.get_finalized_defects(min_hits=1)
