import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status

from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    RoadSegment,
    Contractor,
    CreateIncidentFromDetectionRequest,
    UpdateIncidentStatusRequest,
    GeoLocation,
    PhysicalMetrics,
    AuditLogEntry
)
from app.core.database import db
from app.services.spatial import GeospatialMatcher
from app.services.sla import SLAEngine

router = APIRouter(prefix="/incidents", tags=["Phase 2: Incident Lifecycle & Spatial Management"])
spatial_matcher = GeospatialMatcher()


def create_incident_from_detection_service(request: CreateIncidentFromDetectionRequest) -> Incident:
    """
    Core business logic promoting a Phase 1 detection into an officially registered incident.
    """
    now = datetime.now(timezone.utc)
    incident_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"

    # 1. Spatial Boundary Matching
    road_segment, contractor = spatial_matcher.match_location(
        lat=request.latitude,
        lng=request.longitude,
        road_hint=request.road_name
    )

    # 2. Dynamic SLA & PCI Deduct Engine
    sla_metrics = SLAEngine.calculate_sla(request.severity, now)
    pci_deduct = SLAEngine.compute_pci_deduct(request.defect_type, request.severity)

    # 3. Assemble Official Ticket
    incident = Incident(
        id=incident_id,
        created_at=now,
        defect_type=request.defect_type,
        severity=request.severity,
        status=IncidentStatus.ASSIGNED,
        location=GeoLocation(
            latitude=request.latitude,
            longitude=request.longitude,
            road_name=request.road_name or road_segment.name
        ),
        road_segment=road_segment,
        assigned_contractor=contractor,
        sla_metrics=sla_metrics,
        physical_metrics=PhysicalMetrics(
            surface_area_m2=request.surface_area_m2,
            estimated_depth_m=request.estimated_depth_m,
            volume_m3=request.volume_m3,
            asphalt_required_kg=request.asphalt_required_kg
        ),
        evidence_image_url=request.evidence_image_url,
        pci_deduct_points=pci_deduct,
        audit_trail=[
            AuditLogEntry(
                timestamp=now,
                previous_status=None,
                new_status=IncidentStatus.REPORTED,
                actor="Phase 1 Perception Pipeline",
                notes="Automated computer vision detection"
            ),
            AuditLogEntry(
                timestamp=now,
                previous_status=IncidentStatus.REPORTED,
                new_status=IncidentStatus.ASSIGNED,
                actor="Geospatial Matching Engine",
                notes=f"Assigned to {contractor.name} under {road_segment.name} contract"
            )
        ]
    )

    return db.create_incident(incident)


def update_incident_status_service(incident_id: str, request: UpdateIncidentStatusRequest) -> Incident:
    """
    Core business logic executing a validated lifecycle state transition.
    """
    return db.transition_status(
        incident_id=incident_id,
        new_status=request.new_status,
        actor=request.actor,
        notes=request.notes
    )


@router.get("", response_model=List[Incident])
async def list_incidents(
    status: Optional[IncidentStatus] = Query(None, description="Filter by lifecycle status"),
    severity: Optional[SeverityLevel] = Query(None, description="Filter by severity level"),
    contractor_id: Optional[str] = Query(None, description="Filter by assigned contractor ID"),
    segment_id: Optional[str] = Query(None, description="Filter by road segment ID")
):
    """
    Retrieves all road distress incident tickets with optional multi-criteria filtering.
    """
    return db.list_incidents(
        status=status,
        severity=severity,
        contractor_id=contractor_id,
        segment_id=segment_id
    )


@router.get("/metadata/segments", response_model=List[RoadSegment])
async def list_road_segments():
    """
    Returns registered municipal road segments and spatial jurisdiction boundaries.
    """
    return spatial_matcher.list_all_segments()


@router.get("/metadata/contractors", response_model=List[Contractor])
async def list_contractors():
    """
    Returns registered contractor organizations and performance scorecards.
    """
    return spatial_matcher.list_all_contractors()


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    """
    Retrieves complete incident ticket details including spatial segment, contractor, and audit trail.
    """
    inc = db.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc


@router.post("/create-from-detection", response_model=Incident, status_code=status.HTTP_201_CREATED)
async def create_incident_from_detection(request: CreateIncidentFromDetectionRequest):
    """
    Promotes a raw Phase 1 detection into an officially registered municipal incident ticket.
    Automatically executes spatial boundary matching, contractor assignment, and SLA deadline calculation.
    """
    return create_incident_from_detection_service(request)


@router.patch("/{incident_id}/status", response_model=Incident)
async def update_incident_status(incident_id: str, request: UpdateIncidentStatusRequest):
    """
    Executes a validated lifecycle state machine transition.
    Rejects invalid state jumps (e.g. REPORTED -> CLOSED).
    """
    try:
        return update_incident_status_service(incident_id, request)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

