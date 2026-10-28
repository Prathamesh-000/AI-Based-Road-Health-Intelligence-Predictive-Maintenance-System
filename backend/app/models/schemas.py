from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DefectCategory(str, Enum):
    POTHOLE = "pothole"
    ALLIGATOR_CRACK = "alligator_crack"
    LONGITUDINAL_CRACK = "longitudinal_crack"
    MANHOLE_DEPRESSION = "manhole_depression"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    category: DefectCategory = DefectCategory.POTHOLE
    area_ratio: float = 0.0


class PhysicalMetrics(BaseModel):
    surface_area_m2: float
    estimated_depth_m: float
    volume_m3: float
    asphalt_required_kg: float


class GeoLocation(BaseModel):
    latitude: float
    longitude: float
    elevation_m: Optional[float] = 0.0
    road_name: Optional[str] = "Surveyed Corridor"


class TrackedDefect(BaseModel):
    track_id: int
    category: DefectCategory
    severity: SeverityLevel
    confidence: float
    location: GeoLocation
    physical_metrics: PhysicalMetrics
    best_frame_evidence: str
    timestamp_sec: float
    frame_number: int


class VideoProcessingSummary(BaseModel):
    video_filename: str
    total_frames_analyzed: int
    video_fps: float
    duration_seconds: float
    unique_defects_count: int
    defects: List[TrackedDefect]

