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
        # Use adaptive top_y: dashcam footage (top_y ~50%), low-angle/ground-level footage (top_y ~25%)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # First pass: estimate road area with broad mask to classify scene
        broad_top_y = int(0.25 * h)
        broad_road_pts = np.array([
            [int(0.05 * w), broad_top_y],
            [int(0.95 * w), broad_top_y],
            [int(0.98 * w), h - 1],
            [int(0.02 * w), h - 1]
        ], np.int32)
        broad_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(broad_mask, [broad_road_pts], 255)

        # Classify road brightness to pick detection mode
        road_pixels_broad = gray[broad_mask > 0]
        mean_brightness = float(np.mean(road_pixels_broad)) if len(road_pixels_broad) > 0 else 128.0
        is_dark_road = mean_brightness < 100  # Dirt/mud/gravel roads are dark

        # Adaptive top_y: low-angle (ground-level) cameras see road from ~25% of height
        # Dashcam/windshield cameras see road from ~48% of height
        top_y = int(0.28 * h) if is_dark_road else int(0.48 * h)
        bottom_y = int(0.98 * h)
        road_mask = np.zeros((h, w), dtype=np.uint8)

        # Perspective road corridor (trapezoid narrowing toward vanishing horizon)
        road_pts = np.array([
            [int(0.10 * w), top_y],
            [int(0.90 * w), top_y],
            [int(0.97 * w), bottom_y],
            [int(0.03 * w), bottom_y]
        ], np.int32)
        cv2.fillPoly(road_mask, [road_pts], 255)

        # Mask out detected vehicle exclusion zones
        for vx1, vy1, vx2, vy2 in vehicle_exclusion_zones:
            cv2.rectangle(road_mask, (vx1, vy1), (vx2, vy2), 0, -1)

        # --- Sky/vegetation exclusion: reject very green or very bright sky pixels ---
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Green vegetation mask (hue 35–90, high saturation)
        veg_mask = cv2.inRange(hsv, (35, 60, 40), (90, 255, 255))
        # Sky/cloud mask (very bright, low saturation, blue or white)
        sky_mask = cv2.inRange(hsv, (90, 0, 200), (140, 60, 255))
        white_sky_mask = cv2.inRange(frame, (200, 200, 200), (255, 255, 255))
        # Restrict sky/cloud removal to top half of frame
        top_half = np.zeros((h, w), dtype=np.uint8)
        top_half[:h // 2, :] = 255
        sky_mask = cv2.bitwise_and(cv2.bitwise_or(sky_mask, white_sky_mask), top_half)
        cv2.bitwise_and(road_mask, cv2.bitwise_not(cv2.bitwise_or(veg_mask, sky_mask)), dst=road_mask)

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 3. Dual-Mode Distress Segmentation
        road_gray = cv2.bitwise_and(blurred, blurred, mask=road_mask)
        road_pixels_final = gray[road_mask > 0]
        mean_road = float(np.mean(road_pixels_final)) if len(road_pixels_final) > 0 else 128.0
        std_road = float(np.std(road_pixels_final)) if len(road_pixels_final) > 0 else 30.0

        # Build detection candidate mask using BOTH modes simultaneously
        combined_mask = np.zeros((h, w), dtype=np.uint8)

        # --- Mode A: Dark depression on lighter road surface (dry potholes on asphalt/concrete) ---
        _, dark_thresh = cv2.threshold(road_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        dark_thresh = cv2.bitwise_and(dark_thresh, dark_thresh, mask=road_mask)
        kernel_a = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dark_mask = cv2.morphologyEx(dark_thresh, cv2.MORPH_OPEN, kernel_a)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel_a)

        # --- Mode B: Bright water pools on darker road surface (water-filled potholes on dirt/mud) ---
        # Water-filled potholes appear as bright white/silver patches due to sky reflection.
        # Threshold = mean + 1.2 * std (adaptive to road surface variance).
        bright_threshold = int(min(240, mean_road + max(28, 1.2 * std_road)))
        _, bright_thresh = cv2.threshold(road_gray, bright_threshold, 255, cv2.THRESH_BINARY)
        bright_thresh = cv2.bitwise_and(bright_thresh, bright_thresh, mask=road_mask)
        # Use smaller kernel to preserve small/distant water pools
        water_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
        water_mask = cv2.morphologyEx(bright_thresh, cv2.MORPH_OPEN, water_kernel)
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, water_kernel)

        # Combine both: on dark roads Mode B dominates; on light roads Mode A dominates
        # Both modes contribute across all road types
        combined_mask = cv2.bitwise_or(dark_mask, water_mask)

        # 4. Find contours and validate candidates
        # Smaller min_area to capture small/distant water-filled potholes visible in perspective
        # ~0.00028 * 1280 * 720 = ~258 px (approx 16x16 patch) is the lower bound
        min_area = w * h * 0.00028
        max_area = w * h * 0.22

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        seen_boxes = []  # deduplication

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bw / float(bh)

                # Allow wider aspect ratio for water pools and larger potholes
                if 0.25 <= aspect <= 5.0 and bw < 0.70 * w and bh < 0.55 * h:

                    # Check: candidate must not be dominated by excluded vehicle zone pixels
                    patch_mask = road_mask[by:by + bh, bx:bx + bw]
                    if patch_mask.size == 0 or (np.sum(patch_mask == 0) / float(patch_mask.size)) > 0.15:
                        continue

                    # Center of mass must be on road surface
                    cx, cy = bx + bw // 2, by + bh // 2
                    if road_mask[cy, cx] == 0:
                        continue

                    # Color Saturation Gate: road pavement (asphalt/dirt/mud/water) has low saturation.
                    # Vehicle paint, clothing, grass → reject. Only apply loosely to avoid blocking water.
                    patch_bgr = frame[by:by + bh, bx:bx + bw]
                    if patch_bgr.size > 0:
                        patch_hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV)
                        sat = patch_hsv[:, :, 1]
                        mean_sat = float(np.mean(sat))
                        # Water patches and mud have saturation < 45; bright green leaves = high
                        if mean_sat > 55.0:
                            continue
                        # Also reject if the region is overwhelmingly green (grass/vegetation edge)
                        hue = patch_hsv[:, :, 0]
                        green_ratio = float(np.sum((hue >= 35) & (hue <= 85) & (sat > 50))) / float(patch_bgr.shape[0] * patch_bgr.shape[1])
                        if green_ratio > 0.30:
                            continue

                    # Compute defect signature: determine if this is water-pool or dark depression
                    c_mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(c_mask, [cnt], -1, 255, -1)
                    mean_patch = cv2.mean(gray, mask=c_mask)[0]
                    contrast = mean_patch - mean_road  # positive = brighter than road, negative = darker

                    # Accept if contrast is significant in EITHER direction
                    abs_contrast = abs(contrast)
                    if abs_contrast < 10:
                        continue  # Too similar to road surface - noise

                    # Confidence based on contrast magnitude
                    conf = min(0.96, max(0.62, (abs_contrast / 40.0) + 0.62))

                    category = DefectCategory.POTHOLE
                    if aspect > 2.8:
                        category = DefectCategory.LONGITUDINAL_CRACK

                    # Deduplication: skip if too close to an already-added box
                    is_dup = False
                    for sb in seen_boxes:
                        ox1, oy1, ox2, oy2 = sb
                        overlap_x = max(0, min(bx + bw, ox2) - max(bx, ox1))
                        overlap_y = max(0, min(by + bh, oy2) - max(by, oy1))
                        overlap_area = overlap_x * overlap_y
                        union_area = bw * bh + (ox2 - ox1) * (oy2 - oy1) - overlap_area
                        if union_area > 0 and overlap_area / float(union_area) > 0.45:
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

        return boxes
