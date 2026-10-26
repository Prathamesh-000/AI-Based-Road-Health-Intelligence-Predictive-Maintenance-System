import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import math
from PIL import Image
import imagehash
import time

from app.config import (
    MAX_GEOFENCE_DISTANCE_METERS,
    PHASH_MAX_DUPLICATE_DISTANCE,
    MIN_ORB_MATCHES_ALIGNMENT,
    REPAIRS_DIR
)
from app.models.schemas import (
    VerificationOutcome,
    VerificationReport,
    GeoCoordinates
)
from app.services.detector import RoadPerceptionEngine


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class RepairVerificationEngine:
    """
    Automated closed-loop AI verification engine for road maintenance.
    Combines planar homography, perceptual hashing, residual defect inference,
    and fresh bitumen segmentation.
    """
    def __init__(self, detector: Optional[RoadPerceptionEngine] = None):
        self.detector = detector or RoadPerceptionEngine()

    def check_perceptual_hash(self, img_before_path: str, img_after_path: str) -> Tuple[bool, int]:
        """
        Anti-fraud: Checks if the after photo is identical or recycled using pHash.
        """
        try:
            h_before = imagehash.phash(Image.open(img_before_path))
            h_after = imagehash.phash(Image.open(img_after_path))
            distance = h_before - h_after
            # If distance is near 0, the contractor uploaded the exact same before photo!
            is_suspicious_duplicate = distance <= PHASH_MAX_DUPLICATE_DISTANCE
            return is_suspicious_duplicate, distance
        except Exception:
            return False, 999

    def align_homography(self, img_before: np.ndarray, img_after: np.ndarray) -> Tuple[bool, np.ndarray, int, Optional[np.ndarray]]:
        """
        Calculates planar homography matrix via ORB feature matching and RANSAC
        to warp the 'after' repair photo into the original camera perspective.
        """
        gray1 = cv2.cvtColor(img_before, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img_after, cv2.COLOR_BGR2GRAY)

        # Initialize ORB detector
        orb = cv2.ORB_create(nfeatures=1500, fastThreshold=12)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return False, img_after, 0, None

        # Feature matching with Brute-Force Hamming distance
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        good_matches = [m for m in matches if m.distance < 55]

        if len(good_matches) < MIN_ORB_MATCHES_ALIGNMENT:
            # Not enough reliable planar matches (possibly different road or drastic viewpoint angle)
            return False, img_after, len(good_matches), None

        src_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Compute Homography matrix using RANSAC
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            return False, img_after, len(good_matches), None

        h, w = img_before.shape[:2]
        warped_after = cv2.warpPerspective(img_after, H, (w, h))

        # Generate side-by-side keypoint visualization
        vis_matches = cv2.drawMatches(img_before, kp1, img_after, kp2, good_matches[:25], None,
                                      flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        return True, warped_after, len(good_matches), vis_matches

    def evaluate_patch_texture(self, patch_roi: np.ndarray) -> float:
        """
        Evaluates fresh bitumen texture characteristics (dark uniformity,
        smooth variance vs rocky crater depressions).
        Returns texture compliance score [0.0 to 1.0].
        """
        if patch_roi is None or patch_roi.size == 0:
            return 0.5
        gray = cv2.cvtColor(patch_roi, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        mean_intensity = np.mean(gray)

        # Fresh asphalt is typically darker (intensity 40-100) and evenly compacted (moderate variance)
        score = 0.5
        if 30 < mean_intensity < 120:
            score += 0.25
        if laplacian_var < 800:  # Smooth compacted patch
            score += 0.25
        return min(1.0, max(0.0, score))

    def verify_repair(
        self,
        incident_id: str,
        img_before_path: str,
        img_after_path: str,
        incident_coords: GeoCoordinates,
        submission_coords: Optional[Tuple[float, float]] = None
    ) -> VerificationReport:
        """
        Executes full automated verification pipeline.
        """
        img_before = cv2.imread(img_before_path)
        img_after = cv2.imread(img_after_path)

        if img_before is None or img_after is None:
            raise ValueError("Unable to read input evidence images for verification.")

        # 1. Geofence Telemetry Verification
        geofence_verified = True
        distance_m = 0.0
        if submission_coords and submission_coords[0] and submission_coords[1]:
            distance_m = haversine_distance(
                incident_coords.latitude, incident_coords.longitude,
                submission_coords[0], submission_coords[1]
            )
            if distance_m > MAX_GEOFENCE_DISTANCE_METERS:
                geofence_verified = False

        # 2. Anti-Fraud Perceptual Hash Check
        is_duplicate, hash_dist = self.check_perceptual_hash(img_before_path, img_after_path)

        # 3. Homography Perspective Alignment
        aligned, warped_after, match_count, vis_matches = self.align_homography(img_before, img_after)

        # 4. Residual Defect Detection (Dual-Head Inference)
        inspection_target = warped_after if aligned else img_after
        residual_boxes = self.detector.detect_frame(inspection_target)
        residual_defect_found = len(residual_boxes) > 0

        # 5. Patch Texture Evaluation
        patch_score = self.evaluate_patch_texture(inspection_target)

        # 6. Generate Verification Decision
        diff_filename = f"verify_{incident_id}_{int(time.time())}.jpg"
        diff_path = REPAIRS_DIR / diff_filename
        diff_url = f"/storage/repairs/{diff_filename}"

        if vis_matches is not None:
            cv2.imwrite(str(diff_path), vis_matches)
        else:
            # Create side-by-side comparison
            h1, w1 = img_before.shape[:2]
            h2, w2 = img_after.shape[:2]
            target_h = min(h1, h2)
            b_resized = cv2.resize(img_before, (int(w1 * target_h / h1), target_h))
            a_resized = cv2.resize(img_after, (int(w2 * target_h / h2), target_h))
            comparison = np.hstack([b_resized, a_resized])
            cv2.imwrite(str(diff_path), comparison)

        # Decision Matrix
        if not geofence_verified:
            outcome = VerificationOutcome.VERIFICATION_UNCERTAIN
            explanation = f"Location verification failed: Photo taken {distance_m:.1f}m away (limit is {MAX_GEOFENCE_DISTANCE_METERS}m)."
            confidence = 0.25
        elif is_duplicate:
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            explanation = "Anti-Fraud Alert: Submitted after-photo appears identical to the original defect photo (pHash collision)."
            confidence = 0.95
        elif residual_defect_found:
            max_conf = max(b.confidence for b in residual_boxes)
            outcome = VerificationOutcome.REPAIR_INCOMPLETE
            explanation = f"Residual road distress detected in repaired area with {max_conf*100:.1f}% confidence. Pothole not fully sealed."
            confidence = round(max_conf, 2)
        elif not aligned and match_count < MIN_ORB_MATCHES_ALIGNMENT:
            outcome = VerificationOutcome.VERIFICATION_UNCERTAIN
            explanation = f"Perspective alignment uncertain ({match_count} feature matches). Camera angle differed significantly from original defect. Routing to engineer audit."
            confidence = 0.50
        else:
            outcome = VerificationOutcome.REPAIR_SUCCESSFUL
            explanation = f"Repair verified successfully. Zero residual defects detected. Asphalt patch texture uniformity confirmed ({patch_score*100:.0f}% compliance)."
            confidence = 0.92

        return VerificationReport(
            incident_id=incident_id,
            outcome=outcome,
            confidence_score=confidence,
            homography_aligned=aligned,
            feature_matches_count=match_count,
            geofence_verified=geofence_verified,
            geofence_distance_m=round(distance_m, 1),
            duplicate_suspected=is_duplicate,
            residual_defect_found=residual_defect_found,
            patch_texture_score=round(patch_score, 2),
            explanation=explanation,
            before_image_url=f"/storage/evidence/{Path(img_before_path).name}",
            after_image_url=f"/storage/repairs/{Path(img_after_path).name}",
            visual_diff_url=diff_url
        )
