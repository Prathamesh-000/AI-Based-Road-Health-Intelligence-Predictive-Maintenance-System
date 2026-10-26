from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.schemas import Incident, IncidentStatus
from app.core.database import db

router = APIRouter(prefix="/incidents", tags=["Incident Management"])


@router.get("", response_model=List[Incident])
async def get_all_incidents(status: Optional[IncidentStatus] = Query(None)):
    """
    Retrieves all road distress incidents with optional lifecycle status filtering.
    """
    return db.list_incidents(status=status)


@router.get("/{incident_id}", response_model=Incident)
async def get_incident_by_id(incident_id: str):
    """
    Retrieves a specific incident record.
    """
    inc = db.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return inc
