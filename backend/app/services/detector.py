import os
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional

from app.core.config import CONFIDENCE_THRESHOLD, BASE_DIR
from app.models.schemas import DefectCategory, BoundingBox

try:
    os.environ["YOLO_CONFIG_DIR"] = str((BASE_DIR / "storage").resolve())
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception:
    YOLO_AVAILABLE = False


# COCO classes for vehicles, pedestrians, and transport objects
COCO_VEHICLE_PERSON_CLASSES = {0, 1, 2, 3, 5, 7, 8, 9, 11, 13}
# 0: person, 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck, 8: boat


class RoadPerceptionEngine:
    """
    High-Precision AI Pavement Distress Perception Engine.
    Excludes vehicles, motorcycles, bikes, trucks, cars, and pedestrians,
    isolating genuine asphalt potholes and pavement cracks on the drivable road surface.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if YOLO_AVAILABLE:
            search_paths = [
                model_path,
                "yolov8n.pt",
                str(BASE_DIR / "yolov8n.pt"),
                str(Path.cwd() / "yolov8n.pt"),
                str(Path.cwd() / "backend" / "yolov8n.pt"),
                str(Path(__file__).resolve().parent.parent.parent / "yolov8n.pt")
            ]
            for p in search_paths:
                if p and Path(p).exists():
                    try:
                        self.model = YOLO(p)
                        print(f"[RoadPerceptionEngine] Successfully loaded YOLO weights from {p}")
                        break
                    except Exception as e:
                        print(f"[RoadPerceptionEngine] YOLO load warning for {p}: {e}")

    def detect_frame(self, frame: np.ndarray) -> List[BoundingBox]:
        h, w = frame.shape[:2]
        boxes: List[BoundingBox] = []
        vehicle_exclusion_zones = []

        # 1. Deep Learning Vehicle & Person Localization Pass
        # We run at an ultra-sensitive conf=0.08 to aggressively detect and eliminate ALL vehicles/bikes/trucks/cars
        if self.model:
            try:
                results = self.model(frame, verbose=False, conf=0.08)
                model_names = self.model.names if hasattr(self.model, "names") else {}

                for r in results:
                    for b in r.boxes:
                        coords = b.xyxy[0].cpu().numpy()
                        cls_id = int(b.cls[0].cpu().numpy())
                        cls_name = str(model_names.get(cls_id, "")).lower()

                        # Check if detection is ANY vehicle, bicycle, motorcycle, rider, or pedestrian
                        is_vehicle_or_human = (
                            cls_id in COCO_VEHICLE_PERSON_CLASSES or
                            any(v in cls_name for v in ["car", "truck", "bus", "motorcycle", "bike", "bicycle", "vehicle", "person"])
                        )

                        if is_vehicle_or_human:
                            # Expand exclusion zone to thoroughly cover tires, wheels, exhaust, and undercarriage shadows
                            veh_w = coords[2] - coords[0]
                            veh_h = coords[3] - coords[1]
                            pad_x = max(25, int(veh_w * 0.20))
                            pad_top = max(20, int(veh_h * 0.15))
                            pad_bottom = max(70, int(veh_h * 0.55))  # Cover contact patch & ground shadow

                            vx1 = max(0, int(coords[0]) - pad_x)
                            vy1 = max(0, int(coords[1]) - pad_top)
                            vx2 = min(w, int(coords[2]) + pad_x)
                            vy2 = min(h, int(coords[3]) + pad_bottom)
                            vehicle_exclusion_zones.append((vx1, vy1, vx2, vy2))
                            continue

                        # If custom-trained model has explicit pothole or crack classes
                        if ("pothole" in cls_name or "crack" in cls_name or "defect" in cls_name) and float(b.conf[0]) >= CONFIDENCE_THRESHOLD:
                            box_w = coords[2] - coords[0]
                            box_h = coords[3] - coords[1]
                            cat = DefectCategory.LONGITUDINAL_CRACK if (box_w / max(1.0, box_h) > 2.5) else DefectCategory.POTHOLE
                            boxes.append(BoundingBox(
                                x1=float(coords[0]),
                                y1=float(coords[1]),
                                x2=float(coords[2]),
                                y2=float(coords[3]),
                                confidence=round(float(b.conf[0]), 3),
                                category=cat,
                                area_ratio=round((box_w * box_h) / (w * h), 4)
                            ))

                if boxes:
                    return boxes
            except Exception as e:
                print(f"[RoadPerceptionEngine] Inference warning: {e}")

        # 2. Road Drivable Surface Geometric Extraction
        # Potholes can physically only exist on the drivable road asphalt corridor.
        # Windshield/dashcam camera mount puts the road horizon at ~48-52% of height.
        top_y = int(0.50 * h)
        bottom_y = int(0.98 * h)
        road_mask = np.zeros((h, w), dtype=np.uint8)

        # Perspective road corridor (trapezoid narrowing toward vanishing horizon)
        road_pts = np.array([
            [int(0.18 * w), top_y],
            [int(0.82 * w), top_y],
            [int(0.95 * w), bottom_y],
            [int(0.05 * w), bottom_y]
        ], np.int32)
        cv2.fillPoly(road_mask, [road_pts], 255)

        # Mask out any detected vehicle zones (bikes, cars, trucks, wheels, shadows)
        for vx1, vy1, vx2, vy2 in vehicle_exclusion_zones:
            cv2.rectangle(road_mask, (vx1, vy1), (vx2, vy2), 0, -1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 3. Depression Segmentation on Drivable Road Surface
        road_gray = cv2.bitwise_and(blurred, blurred, mask=road_mask)
        _, otsu = cv2.threshold(road_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        otsu = cv2.bitwise_and(otsu, otsu, mask=road_mask)

        # Morphological filtering to eliminate aggregate grain and minor pavement cracks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dep_mask = cv2.morphologyEx(otsu, cv2.MORPH_OPEN, kernel)
        dep_mask = cv2.morphologyEx(dep_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(dep_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = w * h * 0.002
        max_area = w * h * 0.12

        road_pixels = gray[road_mask > 0]
        mean_road = float(np.mean(road_pixels)) if len(road_pixels) > 0 else 128.0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bw / float(bh)

                # Real road defects have reasonable aspect ratios and bounded dimensions
                if 0.40 <= aspect <= 3.5 and bw < 0.45 * w and bh < 0.40 * h:
                    # Verification 1: Candidate must not overlap with any vehicle exclusion zone
                    patch_mask = road_mask[by:by + bh, bx:bx + bw]
                    if patch_mask.size == 0 or (np.sum(patch_mask == 0) / float(patch_mask.size)) > 0.08:
                        continue

                    # Verification 2: Center of mass must lie inside unoccluded drivable road
                    cx, cy = bx + bw // 2, by + bh // 2
                    if road_mask[cy, cx] == 0:
                        continue

                    # Verification 3: Color Saturation & Chromatic Gate
                    # Real asphalt road pavement has very low color saturation (neutral gray/dark brown).
                    # Tail lights, vehicle paint, clothing, bikes, and pedestrians have vibrant colors / high saturation.
                    patch_bgr = frame[by:by + bh, bx:bx + bw]
                    if patch_bgr.size > 0:
                        patch_hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV)
                        sat = patch_hsv[:, :, 1]
                        if float(np.mean(sat)) > 38.0 or float(np.percentile(sat, 85)) > 75.0:
                            continue

                    # Verification 4: Check surrounding asphalt context
                    # If candidate is a vehicle tire or shadow not caught by YOLO, the area directly above
                    # will have metallic/body reflection or sharp horizontal edge
                    if by > top_y + 20:
                        strip_above = gray[by - 20:by, bx:bx + bw]
                        strip_inside = gray[by:by + 20, bx:bx + bw]
                        if strip_above.mean() > 210 and strip_inside.mean() < 60:
                            continue

                    # Contrast calculation: depressions are significantly darker than road surface
                    c_mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(c_mask, [cnt], -1, 255, -1)
                    mean_dep = cv2.mean(gray, mask=c_mask)[0]
                    contrast = max(0, mean_road - mean_dep)
                    conf = min(0.96, max(0.60, (contrast / 35.0) + 0.60))

                    category = DefectCategory.POTHOLE
                    if aspect > 2.5:
                        category = DefectCategory.LONGITUDINAL_CRACK

                    boxes.append(BoundingBox(
                        x1=float(bx),
                        y1=float(by),
                        x2=float(bx + bw),
                        y2=float(by + bh),
                        confidence=round(conf, 3),
                        category=category,
                        area_ratio=round((bw * bh) / (w * h), 4)
                    ))

        return boxes
