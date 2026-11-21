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
    Supports dual-mode detection:
    - Mode A: Dark depression detection  (dry potholes on light asphalt)
    - Mode B: Bright water-pool detection (water-filled potholes on dark dirt/mud roads)
    Excludes vehicles, motorcycles, bikes, trucks, cars, and pedestrians.
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

    def _classify_scene(self, frame: np.ndarray, road_mask: np.ndarray) -> str:
        """
        Determine whether the road is asphalt/concrete (light surface)
        or dirt/mud/gravel (dark surface) to pick the right detection mode.
        Returns 'dark_road' (needs bright pothole detection) or 'light_road' (needs dark pothole detection).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        road_pixels = gray[road_mask > 0]
        if len(road_pixels) == 0:
            return "light_road"
        mean_brightness = float(np.mean(road_pixels))
        # Dark brown/mud roads typically have mean brightness < 95
        # Light asphalt roads typically have mean brightness >= 90
        return "dark_road" if mean_brightness < 95 else "light_road"

    def detect_frame(self, frame: np.ndarray) -> List[BoundingBox]:
        h, w = frame.shape[:2]
        boxes: List[BoundingBox] = []
        vehicle_exclusion_zones = []

        # 1. Deep Learning Vehicle & Person Localization Pass
        # Run at ultra-sensitive conf=0.08 to aggressively eliminate ALL vehicles/bikes/trucks/cars
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Broad mask to classify scene brightness (excludes top 20% sky)
        broad_top_y = int(0.20 * h)
        broad_road_pts = np.array([
            [int(0.02 * w), broad_top_y],
            [int(0.98 * w), broad_top_y],
            [int(0.99 * w), h - 1],
            [int(0.01 * w), h - 1]
        ], np.int32)
        broad_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(broad_mask, [broad_road_pts], 255)

        # Remove vegetation from broad mask for accurate brightness estimate
        veg_broad = cv2.inRange(hsv, (35, 60, 40), (90, 255, 255))
        broad_mask = cv2.bitwise_and(broad_mask, cv2.bitwise_not(veg_broad))

        road_pixels_broad = gray[broad_mask > 0]
        mean_brightness = float(np.mean(road_pixels_broad)) if len(road_pixels_broad) > 0 else 128.0

        # Dark road = dirt/mud/gravel (mean < 110). Increased threshold for better mud road detection.
        is_dark_road = mean_brightness < 110

        # Adaptive top_y based on camera angle:
        # Ground-level / patrol walker → road fills most of frame, use 20% top
        # Standard dashcam (windshield) → road starts around 45% of frame height
        top_y = int(0.20 * h) if is_dark_road else int(0.45 * h)
        bottom_y = int(0.99 * h)
        road_mask = np.zeros((h, w), dtype=np.uint8)

        # Wide trapezoid road corridor (ground-level footage needs wider polygon)
        road_pts = np.array([
            [int(0.02 * w), top_y],
            [int(0.98 * w), top_y],
            [int(0.99 * w), bottom_y],
            [int(0.01 * w), bottom_y]
        ], np.int32)
        cv2.fillPoly(road_mask, [road_pts], 255)

        # Mask out detected vehicle exclusion zones
        for vx1, vy1, vx2, vy2 in vehicle_exclusion_zones:
            cv2.rectangle(road_mask, (vx1, vy1), (vx2, vy2), 0, -1)

        # --- Vegetation exclusion (grass edges) — only remove high-saturation green ---
        veg_mask = cv2.inRange(hsv, (35, 70, 50), (85, 255, 255))
        # Only remove vegetation pixels; do NOT remove white/bright pixels below mid-frame
        # (they are water-filled potholes, NOT sky)
        sky_blue_mask = cv2.inRange(hsv, (95, 30, 160), (135, 120, 255))
        # Restrict sky removal strictly to top 40% of frame
        sky_zone = np.zeros((h, w), dtype=np.uint8)
        sky_zone[:int(0.40 * h), :] = 255
        sky_blue_mask = cv2.bitwise_and(sky_blue_mask, sky_zone)
        # Combined exclusion: vegetation (anywhere) + sky-blue (top 40% only)
        exclusion_mask = cv2.bitwise_or(veg_mask, sky_blue_mask)
        road_mask = cv2.bitwise_and(road_mask, cv2.bitwise_not(exclusion_mask))

        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # 3. Dual-Mode Distress Segmentation
        road_gray = cv2.bitwise_and(blurred, blurred, mask=road_mask)
        road_pixels_final = gray[road_mask > 0]
        mean_road = float(np.mean(road_pixels_final)) if len(road_pixels_final) > 0 else 128.0
        std_road = float(np.std(road_pixels_final)) if len(road_pixels_final) > 0 else 30.0

        print(f"[Detector] mean_brightness={mean_brightness:.1f}, is_dark_road={is_dark_road}, "
              f"mean_road={mean_road:.1f}, std_road={std_road:.1f}, top_y={top_y}")

        # --- Mode A: Dark depressions (dry potholes, asphalt cracks) ---
        # Otsu threshold on the masked road region finds dark areas
        _, dark_thresh = cv2.threshold(road_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        dark_thresh = cv2.bitwise_and(dark_thresh, dark_thresh, mask=road_mask)
        kernel_a = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dark_mask = cv2.morphologyEx(dark_thresh, cv2.MORPH_OPEN, kernel_a)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel_a)

        # --- Mode B: Bright water pools (sky-reflected puddles in mud/gravel potholes) ---
        # Use a LOWER multiplier (0.9) so we catch water pools even on darker road surfaces.
        # On a mud road (mean=80, std=25): threshold = min(220, 80 + max(22, 0.9*25)) = 102
        # Water pools reflect sky at 180–255 brightness → easily caught.
        bright_threshold = int(min(220, mean_road + max(22, 0.90 * std_road)))
        _, bright_thresh = cv2.threshold(road_gray, bright_threshold, 255, cv2.THRESH_BINARY)
        bright_thresh = cv2.bitwise_and(bright_thresh, bright_thresh, mask=road_mask)
        # Morphological closing fills gaps in water pool blobs
        water_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6, 6))
        water_mask = cv2.morphologyEx(bright_thresh, cv2.MORPH_OPEN, water_kernel)
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, water_kernel)

        # --- Mode C: Edge-contrast detection (only applied within dilated dark+water regions) ---
        # This fills in hairline crack boundaries visible as thin dark edges.
        # Restricted to regions already flagged by Mode A/B to avoid false positives on uniform surfaces.
        pre_candidate = cv2.bitwise_or(dark_mask, water_mask)
        if np.sum(pre_candidate > 0) > 0:
            edges = cv2.Canny(blurred, 40, 100)
            edges = cv2.bitwise_and(edges, edges, mask=road_mask)
            edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            edge_dilated = cv2.dilate(edges, edge_kernel, iterations=2)
            _, edge_filled = cv2.threshold(edge_dilated, 30, 255, cv2.THRESH_BINARY)
            # Only keep edge regions that are NEAR existing Mode A/B candidates
            candidate_dilated = cv2.dilate(pre_candidate, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)), iterations=1)
            edge_filled = cv2.bitwise_and(edge_filled, candidate_dilated)
        else:
            edge_filled = np.zeros((h, w), dtype=np.uint8)

        # Combine all three modes
        combined_mask = cv2.bitwise_or(cv2.bitwise_or(dark_mask, water_mask), edge_filled)
        combined_mask = cv2.bitwise_and(combined_mask, road_mask)

        # 4. Find contours and validate candidates
        # Min area ~0.0002 * frame = ~184 px² at 960x540 (small but real)
        min_area = w * h * 0.0002
        max_area = w * h * 0.30  # Allow larger detections (wide pothole fields)

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"[Detector] contours found={len(contours)}, bright_threshold={bright_threshold}")

        seen_boxes = []  # deduplication

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bw / float(bh)

                # Allow wide range for water pools and large depressions
                if 0.22 <= aspect <= 7.0 and bw < 0.80 * w and bh < 0.70 * h:

                    # Center of mass must be on road surface
                    cx, cy = bx + bw // 2, by + bh // 2
                    if road_mask[cy, cx] == 0:
                        continue

                    # Check: candidate should not be entirely within vehicle exclusion zone
                    patch_mask = road_mask[by:by + bh, bx:bx + bw]
                    if patch_mask.size == 0 or (np.sum(patch_mask == 0) / float(patch_mask.size)) > 0.50:
                        continue

                    # Saturation gate: reject vivid-colored objects (vehicles, clothing, painted markings).
                    # Water pools (gray/white), mud (brown/tan), asphalt (dark gray) all have low saturation.
                    # Raise threshold to 70 to avoid blocking brownish mud-road potholes.
                    patch_bgr = frame[by:by + bh, bx:bx + bw]
                    if patch_bgr.size > 0:
                        patch_hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV)
                        sat = patch_hsv[:, :, 1]
                        mean_sat = float(np.mean(sat))
                        if mean_sat > 70.0:
                            continue
                        # Reject overwhelmingly green regions (roadside grass bleeding into mask)
                        hue = patch_hsv[:, :, 0]
                        green_ratio = float(
                            np.sum((hue >= 35) & (hue <= 85) & (sat > 55))
                        ) / float(patch_bgr.shape[0] * patch_bgr.shape[1])
                        if green_ratio > 0.40:
                            continue

                    # Compute defect contrast relative to road mean
                    c_mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(c_mask, [cnt], -1, 255, -1)
                    mean_patch = cv2.mean(gray, mask=c_mask)[0]
                    contrast = mean_patch - mean_road  # + = brighter (water), − = darker (crack)
                    abs_contrast = abs(contrast)

                    # Lower contrast threshold for muddy roads where contrast is naturally low
                    min_contrast = 8 if is_dark_road else 12
                    if abs_contrast < min_contrast:
                        continue

                    # Confidence based on contrast magnitude and size
                    size_bonus = min(0.08, area / (w * h * 2.0))
                    conf = min(0.97, max(0.62, (abs_contrast / 35.0) * 0.30 + 0.62 + size_bonus))

                    category = DefectCategory.POTHOLE
                    if aspect > 3.0:
                        category = DefectCategory.LONGITUDINAL_CRACK

                    # Deduplication: skip if IoU with existing box > 0.40
                    is_dup = False
                    for sb in seen_boxes:
                        ox1, oy1, ox2, oy2 = sb
                        overlap_x = max(0, min(bx + bw, ox2) - max(bx, ox1))
                        overlap_y = max(0, min(by + bh, oy2) - max(by, oy1))
                        overlap_area = overlap_x * overlap_y
                        union_area = bw * bh + (ox2 - ox1) * (oy2 - oy1) - overlap_area
                        if union_area > 0 and overlap_area / float(union_area) > 0.40:
                            is_dup = True
                            break
                    if is_dup:
                        continue

                    seen_boxes.append((bx, by, bx + bw, by + bh))
                    boxes.append(BoundingBox(
                        x1=float(bx),
                        y1=float(by),
                        x2=float(bx + bw),
                        y2=float(by + bh),
                        confidence=round(conf, 3),
                        category=category,
                        area_ratio=round((bw * bh) / (w * h), 4)
                    ))

        print(f"[Detector] Final detections={len(boxes)}")
        return boxes
