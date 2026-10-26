from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class DefectCategory(str, Enum):
    POTHOLE = "pothole"
    ALLIGATOR_CRACK = "alligator_crack"
    LONGITUDINAL_CRACK = "longitudinal_crack"
    RUTTING = "rutting"
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
    VERIFICATION_UNCERTAIN = "VERIFICATION_UNCERTAIN"

class VerificationOutcome(str, Enum):
    REPAIR_SUCCESSFUL = "REPAIR_SUCCESSFUL"
    REPAIR_INCOMPLETE = "REPAIR_INCOMPLETE"
    VERIFICATION_UNCERTAIN = "VERIFICATION_UNCERTAIN"

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    category: DefectCategory = DefectCategory.POTHOLE
    area_ratio: float = 0.0

class TrackedDefect(BaseModel):
    track_id: int
    category: DefectCategory
    severity: SeverityLevel
    confidence: float
    surface_area_px: float
    estimated_volume_m3: float
    estimated_asphalt_kg: float
    best_frame_path: str
    timestamp_sec: float
    frame_number: int

class GeoCoordinates(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = 5.0
    road_name: Optional[str] = "Arterial Road Segment #4B"

class Contractor(BaseModel):
    id: str
    name: str
    company: str
    email: str
    phone: str
    assigned_zones: List[str]
    performance_score: float = 95.0
    completed_repairs: int = 42

class Incident(BaseModel):
    id: str
    created_at: datetime
    coordinates: GeoCoordinates
    defect_type: DefectCategory
    severity: SeverityLevel
    status: IncidentStatus
    assigned_contractor: Optional[Contractor] = None
    sla_deadline: datetime
    evidence_image_url: str
    estimated_volume_m3: float
    estimated_asphalt_kg: float
    pci_impact: float = 12.5

class RepairSubmission(BaseModel):
    incident_id: str
    contractor_id: str
    repair_notes: str
    submission_lat: Optional[float] = None
    submission_lng: Optional[float] = None
    captured_at: Optional[datetime] = None

class VerificationReport(BaseModel):
    incident_id: str
    outcome: VerificationOutcome
    confidence_score: float
    homography_aligned: bool
    feature_matches_count: int
    geofence_verified: bool
    geofence_distance_m: float
    duplicate_suspected: bool
    residual_defect_found: bool
    patch_texture_score: float
    explanation: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    before_image_url: str
    after_image_url: str
    visual_diff_url: Optional[str] = None
