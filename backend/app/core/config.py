import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
EVIDENCE_DIR = STORAGE_DIR / "evidence"
REPAIRS_DIR = STORAGE_DIR / "repairs"

# Ensure runtime directories exist
for path in [STORAGE_DIR, UPLOAD_DIR, EVIDENCE_DIR, REPAIRS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# System & API Metadata
PROJECT_NAME = "RoadSentinel AI"
PHASE = "Phase 5 - Closed-Loop AI Verification & Anti-Fraud Engine"
VERSION = "1.0.0"
API_PREFIX = "/api/v1"

# Computer Vision & Detection Parameters
CONFIDENCE_THRESHOLD = 0.30
IOU_TRACKING_THRESHOLD = 0.35
MAX_TRACK_AGE = 15
MIN_TRACK_HITS = 1

# Severity Classification (Bounding Box Area Ratio to Frame)
MIN_SEVERITY_AREA_RATIO_HIGH = 0.08    # > 8% of frame = HIGH
MIN_SEVERITY_AREA_RATIO_MED = 0.03     # > 3% of frame = MEDIUM

# Physical Material Constants (ASTM D6433 Reference)
ASPHALT_DENSITY_KG_M3 = 2400.0        # Compacted hot-mix bitumen density
DEFAULT_GSD_METERS_PER_PX = 0.002     # Ground Sampling Distance (2mm per pixel at vehicle focal distance)
DEFAULT_DEPTH_HIGH_M = 0.08           # Severe pothole depth estimate (~8 cm)
DEFAULT_DEPTH_MED_M = 0.05            # Medium pothole depth estimate (~5 cm)
DEFAULT_DEPTH_LOW_M = 0.03            # Minor surface ravelling depth (~3 cm)

# Phase 3: Notification & Dispatch Configuration
NOTIFICATION_COOLING_HOURS = 48.0     # Suppress duplicate alerts for nearby incidents within 48 hours
DUPLICATE_DISTANCE_THRESHOLD_M = 50.0 # Proximity threshold (50m) for spatial deduplication
SMTP_ENABLED = os.getenv("SMTP_ENABLED", "false").lower() in ("true", "1")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.roadsentinel.local")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "dispatch@roadsentinel.ai")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "dispatch@roadsentinel.ai")
SMTP_FROM_NAME = "RoadSentinel AI Dispatch"

# Phase 5: AI Verification & Anti-Fraud Parameters
MAX_GEOFENCE_DISTANCE_METERS = 50.0   # Maximum allowed distance between defect GPS and repair photo GPS
PHASH_MAX_DUPLICATE_DISTANCE = 6      # Hamming distance <= 6 indicates duplicate/recycled stock photo
MIN_ORB_MATCHES_ALIGNMENT = 10        # Minimum valid homography feature matches
MIN_ASPHALT_TEXTURE_COMPLIANCE = 0.60 # Minimum fresh bitumen texture compliance ratio
