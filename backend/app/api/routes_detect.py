import shutil
import uuid
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List

from app.config import UPLOAD_DIR, EVIDENCE_DIR
from app.models.schemas import (
    TrackedDefect,
    Incident,
    IncidentStatus,
    GeoCoordinates
)
from app.services.detector import RoadPerceptionEngine
from app.services.spatial import SpatialAssignmentService
from app.core.database import db

router = APIRouter(prefix="/detect", tags=["Perception & Detection"])
detector = RoadPerceptionEngine()
spatial_service = SpatialAssignmentService()


@router.post("/video", response_model=List[Incident])
async def upload_and_process_video(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(18.5204),
    longitude: Optional[float] = Form(73.8567),
    road_name: Optional[str] = Form("Main Transit Arterial")
):
    """
    Ingests video, runs YOLO + ByteTrack tracking, creates deduplicated incident tickets,
    matches active contractors, and registers them in the database.
    """
    # Save uploaded video
    ext = Path(file.filename).suffix or ".mp4"
    temp_filename = f"vid_{uuid.uuid4().hex[:8]}{ext}"
    temp_path = UPLOAD_DIR / temp_filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        defects = detector.process_video(str(temp_path), sample_interval_frames=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing error: {str(e)}")

    created_incidents: List[Incident] = []

    for d in defects:
        incident_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"
        assigned_contractor, matched_road = spatial_service.match_contractor_for_location(latitude, longitude)
        sla_deadline = spatial_service.calculate_sla_deadline(d.severity)

        inc = Incident(
            id=incident_id,
            created_at=datetime.utcnow(),
            coordinates=GeoCoordinates(
                latitude=latitude,
                longitude=longitude,
                road_name=matched_road or road_name
            ),
            defect_type=d.category,
            severity=d.severity,
            status=IncidentStatus.ASSIGNED,
            assigned_contractor=assigned_contractor,
            sla_deadline=sla_deadline,
            evidence_image_url=d.best_frame_path,
            estimated_volume_m3=d.estimated_volume_m3,
            estimated_asphalt_kg=d.estimated_asphalt_kg,
            pci_impact=round(d.estimated_volume_m3 * 250.0, 1)
        )
        db.create_incident(inc)
        created_incidents.append(inc)

    return created_incidents
