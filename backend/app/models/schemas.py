from enum import Enum
from typing import List, Optional, Dict, Any
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


class IncidentStatus(str, Enum):
    REPORTED = "REPORTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    CLOSED = "CLOSED"


class SLAStatus(str, Enum):
    ON_SCHEDULE = "ON_SCHEDULE"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"


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


class SLAMetrics(BaseModel):
    severity: SeverityLevel
    allowed_hours: int
    deadline: datetime
    status: SLAStatus
    remaining_hours: float


class RoadSegment(BaseModel):
    segment_id: str
    name: str
    zone: str
    contractor_id: str
    bounds: List[float] = Field(description="[min_lat, min_lng, max_lat, max_lng]")
    total_length_km: float


class Contractor(BaseModel):
    id: str
    name: str
    company: str
    email: str
    phone: str
    assigned_zones: List[str]
    performance_score: float = 95.0
    completed_repairs: int = 0


class AuditLogEntry(BaseModel):
    timestamp: datetime
    previous_status: Optional[IncidentStatus]
    new_status: IncidentStatus
    actor: str
    notes: Optional[str] = None


class Incident(BaseModel):
    id: str
    created_at: datetime
    defect_type: DefectCategory
    severity: SeverityLevel
    status: IncidentStatus
    location: GeoLocation
    road_segment: RoadSegment
    assigned_contractor: Optional[Contractor] = None
    sla_metrics: SLAMetrics
    physical_metrics: PhysicalMetrics
    evidence_image_url: str
    pci_deduct_points: float
    audit_trail: List[AuditLogEntry] = []


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


class CreateIncidentFromDetectionRequest(BaseModel):
    defect_type: DefectCategory
    severity: SeverityLevel
    latitude: float
    longitude: float
    road_name: Optional[str] = None
    surface_area_m2: float
    estimated_depth_m: float
    volume_m3: float
    asphalt_required_kg: float
    evidence_image_url: str


class UpdateIncidentStatusRequest(BaseModel):
    new_status: IncidentStatus
    actor: str = "Municipal Dispatcher"
    notes: Optional[str] = None

class CreateIncidentFromDetectionRequest(BaseModel):
    defect_type: DefectCategory
    severity: SeverityLevel
    latitude: float
    longitude: float
    road_name: Optional[str] = None
    surface_area_m2: float
    estimated_depth_m: float
    volume_m3: float
    asphalt_required_kg: float
    evidence_image_url: str


class UpdateIncidentStatusRequest(BaseModel):
    new_status: IncidentStatus
    actor: str = "Municipal Dispatcher"
    notes: Optional[str] = None

