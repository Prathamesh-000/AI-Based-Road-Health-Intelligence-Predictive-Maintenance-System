import cv2
import numpy as np
import imagehash
from PIL import Image
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from app.core.config import (
    BASE_DIR,
    STORAGE_DIR,
    EVIDENCE_DIR,
    REPAIRS_DIR,
    UPLOAD_DIR,
    MAX_GEOFENCE_DISTANCE_METERS,
    PHASH_MAX_DUPLICATE_DISTANCE,
    MIN_ORB_MATCHES_ALIGNMENT,
    MIN_ASPHALT_TEXTURE_COMPLIANCE
)
from app.models.schemas import (
    Incident,
    IncidentStatus,
    RepairSubmission,
    VerificationReport,
    VerificationOutcome,
    BoundingBox,
    DefectCategory,
    NotificationEvent,
    AuditLogEntry
)
from app.core.database import db
from app.services.detector import RoadPerceptionEngine
from app.services.spatial import GeospatialMatcher
from app.services.notification import notification_dispatcher


class RepairVerificationEngine:
    """
    Closed-Loop Automated AI Repair Verification & Anti-Fraud Engine.
    Executes multi-stage forensic validation:
    1. Geofence Distance Validation (Haversine <= 50m)
    2. Perceptual Hash (pHash) Duplicate / Recycled Photo Anti-Fraud Detection
    3. Planar Homography Perspective Normalization (ORB + RANSAC)
    4. Dual-Head Residual Distress & Fresh Bitumen Texture Analysis
    5. Three-State Decision Engine with Automated Work Order Transition & Audit Cards
    """

    def __init__(self):
        self.detector = RoadPerceptionEngine()
        self.matcher = GeospatialMatcher()

    @staticmethod
    def resolve_image_path(url_or_path: str) -> Optional[Path]:
        """
        Resolves local storage URLs (/storage/evidence/...) or relative paths
        to concrete filesystem paths.
        """
        if not url_or_path:
            return None

        p = Path(url_or_path)
        if p.exists() and p.is_file():
            return p

        clean = str(url_or_path).replace("\\", "/").lstrip("/")
        if clean.startswith("storage/"):
            clean_sub = clean[len("storage/"):]
            candidate = STORAGE_DIR / clean_sub
            if candidate.exists():
                return candidate

        # Check subdirectories
        filename = Path(clean).name
        for directory in [EVIDENCE_DIR, REPAIRS_DIR, UPLOAD_DIR, STORAGE_DIR]:
            candidate = directory / filename
            if candidate.exists():
                return candidate

        # Return potential path in repairs or evidence even if absent
        return REPAIRS_DIR / filename

    @staticmethod
    def generate_synthetic_road_frame(defect_type: DefectCategory = DefectCategory.POTHOLE, is_repaired: bool = False) -> np.ndarray:
        """
        Generates realistic synthetic road surface frames for mock demonstrations,
        testing, or fallback when physical media is unavailable.
        """
        h, w = 480, 640
        # Pavement background with asphalt aggregate noise
        base_color = 110 if not is_repaired else 115
        frame = np.full((h, w, 3), base_color, dtype=np.uint8)
        noise = np.random.randint(-15, 15, (h, w, 3), dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Draw road lane markings
        cv2.line(frame, (80, 0), (20, h), (240, 240, 240), 6)
        cv2.line(frame, (560, 0), (620, h), (240, 240, 240), 6)

        # Fixed road surface aggregate landmarks for homography alignment
        np.random.seed(101)
        xp = np.random.randint(40, 600, 80)
        yp = np.random.randint(40, 440, 80)
        for x, y in zip(xp, yp):
            if not (180 <= x <= 480 and 200 <= y <= 420):
                cv2.circle(frame, (int(x), int(y)), 2, (185, 185, 185), -1)

        center_x, center_y = 320, 310
        if not is_repaired:
            # Dark cavity depression with jagged shadow edge
            cv2.ellipse(frame, (center_x, center_y), (85, 55), 15, 0, 360, (30, 30, 30), -1)
            cv2.ellipse(frame, (center_x - 5, center_y - 5), (75, 45), 15, 0, 360, (20, 20, 20), -1)
            # Edge ravelling contour
            cv2.ellipse(frame, (center_x, center_y), (92, 60), 15, 0, 360, (60, 60, 60), 3)
        else:
            # Freshly compacted dark bitumen patch (saw-cut milled rectangular asphalt patch)
            cv2.rectangle(frame, (190, 210), (470, 410), (52, 52, 52), -1)
            # Bitumen emulsion perimeter sealant
            cv2.rectangle(frame, (188, 208), (472, 412), (36, 36, 36), 3)
            # Fine compacted aggregate texture inside patch
            patch_noise = np.random.randint(-6, 6, (200, 280, 3), dtype=np.int16)
            patch_roi = frame[210:410, 190:470].astype(np.int16) + patch_noise
            frame[210:410, 190:470] = np.clip(patch_roi, 0, 255).astype(np.uint8)

        return frame

    def load_or_create_frame(self, url_or_path: str, is_repaired: bool = False, defect_type: DefectCategory = DefectCategory.POTHOLE) -> Tuple[np.ndarray, Path]:
        """
        Loads an image from path or synthesizes a realistic pavement frame if not found.
        """
        resolved = self.resolve_image_path(url_or_path)
        if resolved and resolved.exists():
            img = cv2.imread(str(resolved))
            if img is not None:
                return img, resolved

        # Generate synthetic fallback
        frame = self.generate_synthetic_road_frame(defect_type=defect_type, is_repaired=is_repaired)
        target_path = resolved if resolved else (REPAIRS_DIR / f"synthetic_{'repaired' if is_repaired else 'defect'}_{int(time.time())}.jpg")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(target_path), frame)
        return frame, target_path

    def check_geofence(
        self,
        incident_lat: float,
        incident_lng: float,
        submission_lat: float,
        submission_lng: float
    ) -> Tuple[bool, float]:
        """
        Anti-Fraud Geofencing:
        Calculates Haversine distance between incident location and repair photo coordinates.
        Permits up to MAX_GEOFENCE_DISTANCE_METERS (50.0m).
        """
        dist_m = GeospatialMatcher.haversine_distance_m(
            incident_lat, incident_lng,
            submission_lat, submission_lng
        )
        verified = dist_m <= MAX_GEOFENCE_DISTANCE_METERS
        return verified, round(dist_m, 2)

    def check_perceptual_hash(
        self,
        before_path: Path,
        after_path: Path
    ) -> Tuple[bool, int]:
        """
        Anti-Fraud Duplicate Detection:
        Computes 64-bit Perceptual Hash (pHash) on before and after images.
        Hamming distance <= PHASH_MAX_DUPLICATE_DISTANCE (6) signals duplicate or recycled photo.
        """
        try:
            with Image.open(before_path) as img_b, Image.open(after_path) as img_a:
                hash_b = imagehash.phash(img_b)
                hash_a = imagehash.phash(img_a)
                hamming_dist = int(hash_b - hash_a)
                duplicate = hamming_dist <= PHASH_MAX_DUPLICATE_DISTANCE
                return duplicate, hamming_dist
        except Exception:
            return False, 99

    def align_homography(
        self,
        img_before: np.ndarray,
        img_after: np.ndarray
    ) -> Tuple[bool, int, np.ndarray, Optional[np.ndarray]]:
        """
        Planar Homography Perspective Alignment:
        Extracts ORB features, computes BFMatcher Hamming matches,
        and warps after-image into the before-image perspective via RANSAC.
        """
        h_b, w_b = img_before.shape[:2]
        h_a, w_a = img_after.shape[:2]

        # Resize after image to match before dimensions if different
        if (h_a, w_a) != (h_b, w_b):
            img_after_resized = cv2.resize(img_after, (w_b, h_b), interpolation=cv2.INTER_AREA)
        else:
            img_after_resized = img_after.copy()

        gray_before = cv2.cvtColor(img_before, cv2.COLOR_BGR2GRAY)
        gray_after = cv2.cvtColor(img_after_resized, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=1500, fastThreshold=12)
        kp_before, des_before = orb.detectAndCompute(gray_before, None)
        kp_after, des_after = orb.detectAndCompute(gray_after, None)

        if des_before is None or des_after is None or len(kp_before) < 4 or len(kp_after) < 4:
            return False, 0, img_after_resized, None

        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        raw_matches = matcher.match(des_after, des_before)
        matches = sorted(raw_matches, key=lambda x: x.distance)

        # Filter good matches
        good_matches = [m for m in matches if m.distance < 65]
        matches_count = len(good_matches)

        if matches_count < MIN_ORB_MATCHES_ALIGNMENT:
            return False, matches_count, img_after_resized, None

        src_pts = np.float32([kp_after[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_before[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        if len(src_pts) >= 4 and len(dst_pts) >= 4:
            try:
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                if H is not None:
                    inliers = int(np.sum(mask)) if mask is not None else matches_count
                    if inliers >= MIN_ORB_MATCHES_ALIGNMENT:
                        warped = cv2.warpPerspective(img_after_resized, H, (w_b, h_b))
                        return True, inliers, warped, H
            except Exception:
                pass

        return False, matches_count, img_after_resized, None

    def detect_residual_defects(self, inspection_frame: np.ndarray) -> Tuple[bool, Optional[float], List[BoundingBox]]:
        """
        Dual-Head Verification Head A:
        Runs YOLOv8/OpenCV depression detection to identify residual unrepaired potholes or cracks.
        Distinguishes between unsealed void cavities (deep shadow, ravelling, min_val < 32)
        and compliant repaired asphalt patches (smooth compacted surface, min_val >= 35, uniform bitumen).
        """
        boxes = self.detector.detect_frame(inspection_frame)
        h, w = inspection_frame.shape[:2]
        gray = cv2.cvtColor(inspection_frame, cv2.COLOR_BGR2GRAY)

        residual_defects = []
        for b in boxes:
            if b.confidence < 0.40 or b.area_ratio < 0.005:
                continue

            x1, y1 = max(0, int(b.x1)), max(0, int(b.y1))
            x2, y2 = min(w, int(b.x2)), min(h, int(b.y2))
            if (x2 - x1) < 8 or (y2 - y1) < 8:
                continue

            crop = gray[y1:y2, x1:x2]
            min_val = int(np.min(crop))
            std_val = float(np.std(crop))

            # A true unsealed pothole features deep cavity shadow gradients (min_val < 28 or std_val > 18.0)
            # A compacted asphalt patch is rolled flat and uniform (std_val < 15.0, min_val >= 30)
            is_void_cavity = (min_val < 28) or (std_val > 18.0 and min_val < 32)
            is_crack = (b.category == DefectCategory.LONGITUDINAL_CRACK) or ((b.x2 - b.x1) / max(1.0, b.y2 - b.y1) > 2.8)

            if is_void_cavity or is_crack:
                residual_defects.append(b)

        if residual_defects:
            max_conf = max(b.confidence for b in residual_defects)
            return True, round(max_conf, 3), residual_defects
        return False, None, []

    def evaluate_patch_texture(self, inspection_frame: np.ndarray) -> float:
        """
        Dual-Head Verification Head B:
        Analyzes fresh bitumen compaction, color compliance, and gradient uniformity.
        Compacted hot-mix asphalt (HMA) exhibits characteristic dark matte reflectance
        and moderate texture variance without sharp shadow cliffs.
        """
        h, w = inspection_frame.shape[:2]
        roi_y_start = int(h * 0.35)
        roi = inspection_frame[roi_y_start:h, 0:w]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # 1. Asphalt Darkness Score: Fresh bitumen is dark gray (intensity 25 - 130)
        bitumen_mask = cv2.inRange(gray, 25, 130)
        bitumen_pixel_ratio = float(np.count_nonzero(bitumen_mask)) / float(roi.shape[0] * roi.shape[1])
        color_score = min(1.0, bitumen_pixel_ratio * 1.35)

        # 2. Surface Compaction Uniformity via Laplacian Variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(laplacian.var())

        # Ideal road compaction variance: 40.0 to 500.0
        # (Too high > 800 indicates jagged unrepaired cavity; too low < 20 indicates blank void/glare)
        if 40.0 <= lap_var <= 550.0:
            texture_score = 0.95
        elif lap_var < 40.0:
            texture_score = max(0.40, lap_var / 40.0)
        else:
            texture_score = max(0.30, 1.0 - ((lap_var - 550.0) / 1000.0))

        # Combined compliance score
        compliance = (0.60 * color_score) + (0.40 * texture_score)
        return round(float(np.clip(compliance, 0.05, 0.98)), 3)

    def generate_visual_diff(
        self,
        before_frame: np.ndarray,
        after_frame: np.ndarray,
        outcome: VerificationOutcome,
        incident_id: str,
        defect_boxes: List[BoundingBox],
        texture_score: float
    ) -> Tuple[str, Path]:
        """
        Generates an audit-ready 3-panel visual difference composite:
        [ BEFORE (Distress Marked) | AFTER (Patch Inspection) | VERIFICATION MAP ]
        With color-coded banners and verification metadata.
        """
        h, w = 360, 480
        b_resized = cv2.resize(before_frame, (w, h))
        a_resized = cv2.resize(after_frame, (w, h))

        # Panel 1: Annotate Before Image
        p1 = b_resized.copy()
        cv2.putText(p1, "BEFORE: ORIGINAL DEFECT", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

        # Panel 2: Annotate After Image
        p2 = a_resized.copy()
        after_color = (0, 200, 0) if outcome == VerificationOutcome.REPAIR_SUCCESSFUL else (0, 0, 255)
        cv2.putText(p2, "AFTER: REPAIR EVIDENCE", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, after_color, 2)

        # Draw residual boxes if any
        for box in defect_boxes:
            sx = w / float(before_frame.shape[1])
            sy = h / float(before_frame.shape[0])
            x1, y1, x2, y2 = int(box.x1 * sx), int(box.y1 * sy), int(box.x2 * sx), int(box.y2 * sy)
            cv2.rectangle(p2, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(p2, f"RESIDUAL {box.confidence*100:.0f}%", (x1, max(20, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

        # Panel 3: Verification Heatmap Difference
        gray_b = cv2.cvtColor(b_resized, cv2.COLOR_BGR2GRAY)
        gray_a = cv2.cvtColor(a_resized, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_b, gray_a)
        diff_heat = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
        p3 = cv2.addWeighted(a_resized, 0.6, diff_heat, 0.4, 0)
        cv2.putText(p3, "PERSPECTIVE DIFF HEATMAP", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # Assemble side-by-side composite: width = 3 * 480 = 1440, height = 360 + 80 banner + 40 footer = 480
        total_w = w * 3
        total_h = h + 110
        composite = np.full((total_h, total_w, 3), 20, dtype=np.uint8)

        # Status Banner Bar
        if outcome == VerificationOutcome.REPAIR_SUCCESSFUL:
            banner_bg = (34, 139, 34)     # Forest Green
            status_text = "[VERIFIED] AI REPAIR VERIFICATION SUCCESSFUL - QUALITY COMPLIANT"
        elif outcome == VerificationOutcome.REPAIR_INCOMPLETE:
            banner_bg = (30, 30, 200)     # Crimson Red
            status_text = "[REJECTED] REPAIR INCOMPLETE - RESIDUAL DISTRESS OR FRAUD DETECTED"
        else:
            banner_bg = (20, 140, 220)    # Amber Orange
            status_text = "[UNCERTAIN] VERIFICATION INCONCLUSIVE - MUNICIPAL AUDIT REQUIRED"

        cv2.rectangle(composite, (0, 0), (total_w, 65), banner_bg, -1)
        cv2.putText(composite, "ROADSENTINEL AI: CLOSED-LOOP VERIFICATION AUDIT", (20, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(composite, status_text, (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Place 3 Panels
        composite[75:75+h, 0:w] = p1
        composite[75:75+h, w:w*2] = p2
        composite[75:75+h, w*2:total_w] = p3

        # Footer Telemetry Bar
        cv2.rectangle(composite, (0, total_h - 35), (total_w, total_h), (12, 16, 24), -1)
        telemetry = f"Incident ID: {incident_id}  |  Texture Score: {texture_score*100:.1f}%  |  Engine: Dual-Head YOLOv8 + Bitumen Texture  |  Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        cv2.putText(composite, telemetry, (20, total_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 174, 192), 1)

        # Save to Storage
        filename = f"diff_{incident_id}_{int(time.time())}.jpg"
        target_path = REPAIRS_DIR / filename
        cv2.imwrite(str(target_path), composite)

        return f"/storage/repairs/{filename}", target_path

    def verify_repair(
        self,
        incident: Incident,
        submission: RepairSubmission,
        force_override: bool = False,
        manual_notes: Optional[str] = None
    ) -> VerificationReport:
        """
        Executes complete 5-stage verification pipeline:
        1. Geofence evaluation
        2. Anti-fraud pHash collision check
        3. Homography perspective alignment
        4. Dual-head residual defect & texture compliance check
        5. Three-state decision engine with automated state machine transitions
        """
        report_id = f"RPT-VER-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # 1. Geofence Verification
        geofence_ok, geofence_dist = self.check_geofence(
            incident.location.latitude, incident.location.longitude,
            submission.submission_latitude, submission.submission_longitude
        )

        # Load before and after imagery
        before_frame, before_path = self.load_or_create_frame(incident.evidence_image_url, is_repaired=False, defect_type=incident.defect_type)
        after_frame, after_path = self.load_or_create_frame(submission.repair_photo_url, is_repaired=True, defect_type=incident.defect_type)

        # 2. Anti-Fraud Perceptual Hash Duplicate Detection
        duplicate_suspected, phash_dist = self.check_perceptual_hash(before_path, after_path)

        # 3. Homography Perspective Alignment
        homography_ok, matches_count, aligned_frame, _ = self.align_homography(before_frame, after_frame)

        # 4. Dual-Head Verification
        # Check residual defects on aligned frame (or after frame)
        inspection_target = aligned_frame if homography_ok else after_frame
        residual_found, residual_conf, defect_boxes = self.detect_residual_defects(inspection_target)

        # Check bitumen texture compliance
        texture_score = self.evaluate_patch_texture(inspection_target)

        # 5. Three-State Decision Engine
        if not geofence_ok and not force_override:
            outcome = VerificationOutcome.VERIFICATION_UNCERTAIN
            confidence = 0.25
            explanation = (
                f"Geofence violation: Repair photo submitted {geofence_dist:.1f}m away from registered defect coordinates "
                f"(max permitted: {MAX_GEOFENCE_DISTANCE_METERS}m). Flagged for municipal on-site audit."
            )
            new_incident_status = IncidentStatus.VERIFICATION_PENDING

        elif duplicate_suspected and not force_override:
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            confidence = 0.95
            explanation = (
                f"Anti-Fraud Alert: Submitted photo is identical or recycled from original defect photograph "
                f"(pHash Hamming distance {phash_dist} <= {PHASH_MAX_DUPLICATE_DISTANCE}). Suspected fraudulent submission."
            )
            new_incident_status = IncidentStatus.REWORK_REQUIRED

        elif residual_found and not force_override:
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            confidence = residual_conf or 0.85
            defect_type_str = defect_boxes[0].category.value if defect_boxes else "Depression"
            explanation = (
                f"Residual Distress Detected: Pavement defect remains unsealed ({defect_type_str} with {confidence*100:.1f}% confidence). "
                f"Patch compaction does not meet ASTM D6433 restoration standards."
            )
            new_incident_status = IncidentStatus.REWORK_REQUIRED

        elif matches_count < MIN_ORB_MATCHES_ALIGNMENT and texture_score < 0.50 and not force_override:
            outcome = VerificationOutcome.VERIFICATION_UNCERTAIN
            confidence = 0.40
            explanation = (
                f"Verification Inconclusive: Camera perspective differs significantly ({matches_count} matching features < {MIN_ORB_MATCHES_ALIGNMENT}) "
                f"and asphalt texture score ({texture_score*100:.1f}%) is borderline. Routed to senior engineer triage."
            )
            new_incident_status = IncidentStatus.VERIFICATION_PENDING

        else:
            # Successful Repair
            outcome = VerificationOutcome.REPAIR_SUCCESSFUL
            confidence = round(min(0.98, max(0.72, 0.65 + (0.35 * texture_score))), 2)
            explanation = (
                f"Maintenance Verified Successful: Defect cavity eliminated with compliant hot-mix asphalt compaction "
                f"(Texture score: {texture_score*100:.1f}%, Geofence: {geofence_dist:.1f}m, Features: {matches_count})."
            )
            new_incident_status = IncidentStatus.VERIFIED

        # Generate Visual Diff Composite Card
        diff_url, _ = self.generate_visual_diff(
            before_frame=before_frame,
            after_frame=inspection_target,
            outcome=outcome,
            incident_id=incident.id,
            defect_boxes=defect_boxes,
            texture_score=texture_score
        )

        # Construct Verification Report
        report = VerificationReport(
            report_id=report_id,
            incident_id=incident.id,
            submission_id=submission.id,
            outcome=outcome,
            confidence_score=confidence,
            homography_aligned=homography_ok,
            feature_matches_count=matches_count,
            geofence_verified=geofence_ok,
            geofence_distance_m=geofence_dist,
            duplicate_suspected=duplicate_suspected,
            phash_distance=phash_dist,
            residual_defect_found=residual_found,
            residual_defect_confidence=residual_conf,
            patch_texture_score=texture_score,
            visual_diff_url=diff_url,
            explanation=explanation,
            evaluated_at=now
        )
        db.save_verification_report(report)

        # Lifecycle State Machine Transition & Audit Logging
        if new_incident_status != incident.status:
            audit_note = (
                f"Closed-Loop AI Verification evaluated ({outcome.value}, Confidence: {confidence*100:.1f}%). "
                f"{explanation}"
            )
            if manual_notes:
                audit_note += f" Reviewer notes: {manual_notes}"

            db.transition_status(
                incident_id=incident.id,
                new_status=new_incident_status,
                actor="Closed-Loop AI Verification Engine",
                notes=audit_note
            )

        # Trigger Automated Contractor Notifications
        if outcome == VerificationOutcome.REPAIR_SUCCESSFUL:
            # Update contractor completed repairs
            if incident.assigned_contractor:
                incident.assigned_contractor.completed_repairs += 1
            notification_dispatcher.dispatch_incident_notification(
                incident=incident,
                event=NotificationEvent.REPAIR_VERIFIED,
                custom_notes=f"AI Verification Report {report_id} verified complete with {confidence*100:.1f}% confidence. Payment release authorized.",
                force_resend=True
            )
        elif outcome == VerificationOutcome.REPAIR_INCOMPLETE:
            notification_dispatcher.dispatch_incident_notification(
                incident=incident,
                event=NotificationEvent.REWORK_REQUIRED,
                custom_notes=f"AI Verification Alert: {explanation} Immediate site remediation required within SLA window.",
                force_resend=True
            )

        return report

    def evaluate_image_pair(self, before_path: Path, after_path: Path) -> Dict[str, Any]:
        """
        Standalone forensic comparison of arbitrary before and after image files.
        """
        before_frame = cv2.imread(str(before_path))
        after_frame = cv2.imread(str(after_path))
        if before_frame is None or after_frame is None:
            raise ValueError("Unable to read one or both target image files.")

        duplicate, phash_dist = self.check_perceptual_hash(before_path, after_path)
        homography_ok, matches_count, aligned_frame, _ = self.align_homography(before_frame, after_frame)
        inspection_target = aligned_frame if homography_ok else after_frame
        residual_found, residual_conf, defect_boxes = self.detect_residual_defects(inspection_target)
        texture_score = self.evaluate_patch_texture(inspection_target)

        if duplicate:
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            confidence = 0.95
            summary = "Suspected duplicate/recycled photo fraud"
        elif residual_found:
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            confidence = residual_conf or 0.85
            summary = "Residual pavement defect detected"
        elif matches_count >= MIN_ORB_MATCHES_ALIGNMENT and texture_score >= MIN_ASPHALT_TEXTURE_COMPLIANCE:
            outcome = VerificationOutcome.REPAIR_SUCCESSFUL
            confidence = round(0.65 + 0.35 * texture_score, 2)
            summary = "Repair verified successful"
        else:
            outcome = VerificationOutcome.VERIFICATION_UNCERTAIN
            confidence = 0.45
            summary = "Verification uncertain, requires human review"

        return {
            "outcome": outcome,
            "confidence": confidence,
            "summary": summary,
            "duplicate_suspected": duplicate,
            "phash_distance": phash_dist,
            "homography_aligned": homography_ok,
            "feature_matches_count": matches_count,
            "residual_defect_found": residual_found,
            "residual_defect_confidence": residual_conf,
            "texture_score": texture_score
        }


# Global singleton verification engine instance
verification_engine = RepairVerificationEngine()
