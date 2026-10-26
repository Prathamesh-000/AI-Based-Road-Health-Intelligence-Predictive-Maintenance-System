from fastapi import APIRouter
from typing import Dict, Any, List

from app.models.schemas import Incident, IncidentStatus
from app.core.database import db
from app.services.spatial import SpatialAssignmentService

router = APIRouter(prefix="/public", tags=["Public Portal & Civic Intelligence"])
spatial_service = SpatialAssignmentService()


@router.get("/portal", response_model=List[Incident])
async def get_public_incidents_feed():
    """
    Public road status feed showing transparent verification lifecycle.
    """
    return db.list_incidents()


@router.get("/rhi", response_model=Dict[str, Any])
async def get_road_health_index():
    """
    Returns aggregate Pavement Condition Index (PCI) / Road Health Index (RHI)
    for city dashboard visualization.
    """
    incidents = db.list_incidents()
    return spatial_service.calculate_road_health_index(incidents)
