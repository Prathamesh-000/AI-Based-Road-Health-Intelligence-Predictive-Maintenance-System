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
PHASE = "Phase 1 - Perception, Telemetry & Volumetric Engine"
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

