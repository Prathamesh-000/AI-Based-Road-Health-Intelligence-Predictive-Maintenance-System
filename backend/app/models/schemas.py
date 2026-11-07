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


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    SMS = "SMS"


class NotificationStatus(str, Enum):
    SENT = "SENT"
    SUPPRESSED = "SUPPRESSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class NotificationEvent(str, Enum):
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
    SLA_REMINDER = "SLA_REMINDER"
    SLA_BREACHED = "SLA_BREACHED"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    REPAIR_VERIFIED = "REPAIR_VERIFIED"


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


class ContractorScorecard(BaseModel):
    contractor_id: str
    contractor_name: str
    company: str
    email: str
    phone: str
    assigned_zones: List[str]
    total_assigned: int
    in_progress: int
    pending_verification: int
    verified_completed: int
    rework_required: int
    on_time_completion_rate: float
    performance_score: float


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


class RepairSubmission(BaseModel):
    id: str
    incident_id: str
    contractor_id: str
    submitted_at: datetime
    submission_latitude: float
    submission_longitude: float
    submission_accuracy_m: Optional[float] = 5.0
    repair_photo_url: str
    asphalt_mix_type: Optional[str] = "Hot-Mix Asphalt (HMA)"
    asphalt_used_kg: Optional[float] = None
    engineering_notes: Optional[str] = None
    exif_metadata: Optional[Dict[str, Any]] = None


class VerificationReport(BaseModel):
    report_id: str
    incident_id: str
    submission_id: str
    outcome: VerificationOutcome
    confidence_score: float
    homography_aligned: bool
    feature_matches_count: int
    geofence_verified: bool
    geofence_distance_m: float
    duplicate_suspected: bool
    phash_distance: int
    residual_defect_found: bool
    residual_defect_confidence: Optional[float] = None
    patch_texture_score: float
    visual_diff_url: Optional[str] = None
    explanation: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class RepairSubmissionResponse(BaseModel):
    submission: RepairSubmission
    incident_id: str
    previous_status: IncidentStatus
    new_status: IncidentStatus
    message: str
    verification_report: Optional[VerificationReport] = None


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


class NotificationLog(BaseModel):
    id: str
    incident_id: str
    contractor_id: str
    recipient_email: str
    event: NotificationEvent
    channel: NotificationChannel = NotificationChannel.EMAIL
    status: NotificationStatus
    subject: str
    html_content: str
    plain_text: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    suppression_reason: Optional[str] = None
    attempt_count: int = 1
    delivery_response: Optional[str] = None


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


class AcknowledgeIncidentRequest(BaseModel):
    actor: str = "Contractor Maintenance Crew"
    notes: Optional[str] = "Dispatched repair vehicle to site"


class DispatchIncidentRequest(BaseModel):
    event: NotificationEvent = NotificationEvent.INCIDENT_ASSIGNED
    channel: NotificationChannel = NotificationChannel.EMAIL
    custom_notes: Optional[str] = None
    force_resend: bool = False


class VerifyIncidentRequest(BaseModel):
    force_override: bool = False
    manual_notes: Optional[str] = None


# Phase 6: Public Transparency & Civic Intelligence Models
class RoadHealthRating(str, Enum):
    EXCELLENT = "EXCELLENT"       # 85 - 100
    GOOD = "GOOD"                 # 70 - 84
    FAIR = "FAIR"                 # 55 - 69
    POOR = "POOR"                 # 40 - 54
    VERY_POOR = "VERY_POOR"       # 25 - 39
    FAILED = "FAILED"             # 0 - 24


class RoadSegmentHealth(BaseModel):
    segment_id: str
    name: str
    zone: str
    contractor_id: str
    contractor_name: str
    total_length_km: float
    active_defects_count: int
    verified_repairs_count: int
    total_pci_deduct: float
    rhi_score: float
    health_rating: RoadHealthRating


class MunicipalRHIResponse(BaseModel):
    city_name: str = "Metro Infrastructure Network"
    overall_rhi_score: float
    health_rating: RoadHealthRating
    total_incidents_logged: int
    active_hazards_count: int
    in_remediation_count: int
    verified_repairs_count: int
    repaired_pci_restored: float
    asphalt_laid_kg: float
    evaluated_at: datetime
    segment_breakdown: List[RoadSegmentHealth]


class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


class PublicAuditCard(BaseModel):
    incident_id: str
    defect_type: DefectCategory
    severity: SeverityLevel
    status: IncidentStatus
    road_name: str
    zone: str
    contractor_name: str
    latitude: float
    longitude: float
    reported_at: datetime
    verified_at: Optional[datetime] = None
    evidence_image_url: str
    repair_photo_url: Optional[str] = None
    visual_diff_url: Optional[str] = None
    confidence_score: Optional[float] = None
    feature_matches_count: Optional[int] = None
    texture_compliance_score: Optional[float] = None
    explanation: Optional[str] = None
    asphalt_used_kg: Optional[float] = None
