import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
EVIDENCE_DIR = STORAGE_DIR / "evidence"
REPAIRS_DIR = STORAGE_DIR / "repairs"

for d in [STORAGE_DIR, UPLOAD_DIR, EVIDENCE_DIR, REPAIRS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# App Settings
PROJECT_NAME = "RoadSentinel AI"
VERSION = "1.0.0"
API_PREFIX = "/api/v1"

# Computer Vision & Detection Thresholds
CONFIDENCE_THRESHOLD = 0.30
IOU_THRESHOLD = 0.45
MIN_SEVERITY_AREA_RATIO_HIGH = 0.08    # > 8% of frame = High
MIN_SEVERITY_AREA_RATIO_MED = 0.03     # > 3% of frame = Medium

# AI Verification & Anti-Fraud Config
MAX_GEOFENCE_DISTANCE_METERS = 50.0   # Max allowed distance between defect & repair photo
PHASH_MAX_DUPLICATE_DISTANCE = 6      # Hamming distance <= 6 indicates duplicate/recycled image
MIN_ORB_MATCHES_ALIGNMENT = 10        # Minimum valid homography feature matches
MIN_ASPHALT_TEXTURE_RATIO = 0.35      # Minimum detected fresh bitumen patch texture ratio

# SLA Durations (in hours)
SLA_HOURS = {
    "HIGH": 24,
    "MEDIUM": 72,
    "LOW": 168
}
