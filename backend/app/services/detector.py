import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional

from app.core.config import CONFIDENCE_THRESHOLD, BASE_DIR
from app.models.schemas import DefectCategory, BoundingBox

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class RoadPerceptionEngine:
    """
    AI Perception Engine supporting YOLOv8 deep learning inference with
    multi-scale OpenCV computer vision fallback for pavement distress localization.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if YOLO_AVAILABLE:
            search_paths = [
                model_path,
                "yolov8n.pt",
                str(BASE_DIR / "yolov8n.pt"),
                str(Path.cwd() / "yolov8n.pt")
            ]
            for p in search_paths:
                if p and Path(p).exists():
                    try:
                        self.model = YOLO(p)
                        print(f"[RoadPerceptionEngine] Loaded YOLO weights from {p}")
                        break
                    except Exception as e:
                        print(f"[RoadPerceptionEngine] YOLO load warning: {e}")

    def detect_frame(self, frame: np.ndarray) -> List[BoundingBox]:
        h, w = frame.shape[:2]
        boxes: List[BoundingBox] = []

        # 1. Deep Learning Inference Pass
        if self.model:
            try:
                results = self.model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
                for r in results:
                    for b in r.boxes:
                        coords = b.xyxy[0].cpu().numpy()
                        conf = float(b.conf[0].cpu().numpy())
                        cls_id = int(b.cls[0].cpu().numpy())
                        box_w = coords[2] - coords[0]
                        box_h = coords[3] - coords[1]
                        area_ratio = (box_w * box_h) / (w * h)

                        category = DefectCategory.POTHOLE
                        if box_w / max(1.0, box_h) > 2.5:
                            category = DefectCategory.LONGITUDINAL_CRACK

                        boxes.append(BoundingBox(
                            x1=float(coords[0]),
                            y1=float(coords[1]),
                            x2=float(coords[2]),
                            y2=float(coords[3]),
                            confidence=round(conf, 3),
                            category=category,
                            area_ratio=round(area_ratio, 4)
                        ))
                if boxes:
                    return boxes
            except Exception:
                pass

        # 2. Robust Computer Vision Fallback (Depression & Gradient Analysis)
        # Inspects road region of interest (lower 65% of camera field)
        roi_y_start = int(h * 0.35)
        roi = frame[roi_y_start:h, 0:w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Multi-scale Otsu + adaptive depression segmentation
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10)
        combined = cv2.bitwise_or(otsu, adaptive)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        morph = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        morph = cv2.morphologyEx(morph, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (w * h * 0.003):  # Filter out pavement aggregate grain noise
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect_ratio = bw / float(bh)

                if 0.3 < aspect_ratio < 4.5:
                    real_y1 = roi_y_start + by
                    real_y2 = real_y1 + bh
                    area_ratio = (bw * bh) / (w * h)

                    # Contrast calculation: depressions are darker than surrounding pavement
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

