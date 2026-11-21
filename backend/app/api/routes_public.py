from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    MunicipalRHIResponse,
    GeoJSONFeatureCollection,
    PublicAuditCard,
    RoadSegmentHealth,
    CavityMesh3DResponse
)
from app.services.civic import civic_engine
from app.services.volumetric_3d import volumetric_3d_service
from app.core.database import db


router = APIRouter(prefix="/public", tags=["Phase 6: Public Transparency Portal & Civic Intelligence"])


@router.get("/rhi", response_model=MunicipalRHIResponse, summary="Get Municipal Road Health Index (PCI)")
def get_municipal_road_health_index():
    """
    Computes and returns the real-time ASTM D6433 Pavement Condition Index (PCI) /
    Road Health Index (RHI) for the municipal road network.
    Includes overall rating, total active hazards, restored deduct points, and segment breakdowns.
    """
    return civic_engine.compute_municipal_rhi()


@router.get("/hazards", response_model=GeoJSONFeatureCollection, summary="Get Active Road Hazards GeoJSON Feed")
def get_hazards_geojson():
    """
    Returns an RFC 7946 standard GeoJSON FeatureCollection containing all active,
    unrepaired road distress incidents.
    Formatted for direct ingestion by public navigation providers (Waze, OpenStreetMap, Google Maps)
    and citizen GIS maps.
    """
    return civic_engine.generate_hazard_geojson()


@router.get("/audit-feed", response_model=List[PublicAuditCard], summary="Get Public Before/After Audit Feed")
def get_public_audit_feed(
    limit: int = Query(50, ge=1, le=200, description="Maximum audit items to return")
):
    """
    Retrieves transparent before-and-after audit cards for resolved and inspected incidents.
    Includes original distress photographs, completed repair evidence,
    AI homography visual diffs, and verification telemetry stamps.
    """
    return civic_engine.get_public_audit_feed(limit=limit)


@router.get("/audit-card/{incident_id}", response_model=PublicAuditCard, summary="Get Public Audit Card for Incident")
def get_incident_audit_card(incident_id: str):
    """
    Retrieves the complete public audit card and AI verification record for a specific incident.
    """
    card = civic_engine.get_incident_audit_card(incident_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return card


@router.get("/segments", response_model=List[RoadSegmentHealth], summary="List Road Corridor Health Scores")
def get_road_segments_health():
    """
    Returns health indices, active defect counts, and assigned maintenance contractors
    for all registered municipal road corridors.
    """
    rhi_data = civic_engine.compute_municipal_rhi()
    return rhi_data.segment_breakdown


@router.get("/incidents/{incident_id}/3d-mesh", response_model=CavityMesh3DResponse, summary="Get 3D Cavity Topography for Incident")
def get_public_incident_3d_mesh(
    incident_id: str,
    grid_size: int = Query(40, ge=20, le=80, description="Mesh grid resolution")
):
    """
    Public endpoint returning interactive 3D topography heightmap, cross-sections,
    and material sizing metrics for citizen inspection.
    """
    inc = db.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return volumetric_3d_service.generate_cavity_mesh(incident_id=incident_id, grid_size=grid_size)


@router.get("/generate-3d-mesh", response_model=CavityMesh3DResponse, summary="Generate On-the-Fly 3D Cavity Topography")
def generate_public_3d_mesh(
    defect_type: str = Query("pothole", description="Defect classification"),
    severity: str = Query("HIGH", description="Defect severity"),
    surface_area_m2: float = Query(0.55, description="Surface area in m2"),
    estimated_depth_m: float = Query(0.085, description="Estimated depth in meters"),
    road_name: Optional[str] = Query(None, description="Road corridor name"),
    grid_size: int = Query(40, ge=20, le=80, description="Mesh grid resolution")
):
    """
    Generates on-the-fly 3D mesh topography from patrol detections before ticket creation.
    """
    return volumetric_3d_service.generate_cavity_mesh(
        defect_type=defect_type,
        severity=severity,
        road_name=road_name,
        surface_area_m2=surface_area_m2,
        estimated_depth_m=estimated_depth_m,
        grid_size=grid_size
    )

