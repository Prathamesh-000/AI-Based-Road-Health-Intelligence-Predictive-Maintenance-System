import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional

from app.config import REPAIRS_DIR, EVIDENCE_DIR, BASE_DIR
from app.models.schemas import (
    Contractor,
    Incident,
    IncidentStatus,
    VerificationOutcome,
    VerificationReport
)
from app.core.database import db
from app.services.verification import RepairVerificationEngine

router = APIRouter(prefix="/contractors", tags=["Contractor Dashboard & Verification"])
verifier = RepairVerificationEngine()


@router.get("", response_model=List[Contractor])
async def list_contractors():
    """
    Returns list of authorized contractors and current scorecard metrics.
    """
    return list(db.contractors.values())


@router.get("/{contractor_id}/assigned", response_model=List[Incident])
async def list_assigned_incidents(contractor_id: str):
    """
    Returns incidents assigned to a specific contractor organization.
    """
    incidents = db.list_incidents()
    return [i for i in incidents if i.assigned_contractor and i.assigned_contractor.id == contractor_id]


@router.post("/submit-repair")
async def submit_repair_evidence(
    incident_id: str = Form(...),
    contractor_id: str = Form(...),
    notes: str = Form("Pothole patched using standard hot-mix asphalt compaction."),
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None)
):
    """
    Contractor submits repair evidence. The system immediately executes AI-Powered
    verification (anti-fraud check, homography perspective alignment, residual defect check).
    """
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident ID not found.")

    # Save repair after-image
    ext = Path(file.filename).suffix or ".jpg"
    after_filename = f"repair_{incident_id}_{uuid.uuid4().hex[:6]}{ext}"
    after_path = REPAIRS_DIR / after_filename

    with open(after_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Locate before-image path
    before_rel = incident.evidence_image_url.replace("/storage/", "")
    before_path = BASE_DIR / "storage" / before_rel

    # If before image file doesn't exist on disk yet (e.g. simulated initial seed), create a mock baseline
    if not before_path.exists():
        import cv2
        import numpy as np
        mock_before = np.full((480, 640, 3), 90, dtype=np.uint8)
        # Draw a synthetic pothole
        cv2.circle(mock_before, (320, 240), 60, (30, 30, 30), -1)
        cv2.ellipse(mock_before, (320, 240), (75, 45), 20, 0, 360, (20, 20, 20), -1)
        before_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(before_path), mock_before)

    # Trigger Automated Verification Engine
    submission_coords = (latitude, longitude) if latitude and longitude else (incident.coordinates.latitude, incident.coordinates.longitude)
    report = verifier.verify_repair(
        incident_id=incident_id,
        img_before_path=str(before_path),
        img_after_path=str(after_path),
        incident_coords=incident.coordinates,
        submission_coords=submission_coords
    )

    # Update Incident State Machine
    if report.outcome == VerificationOutcome.REPAIR_SUCCESSFUL:
        incident.status = IncidentStatus.VERIFIED
        if incident.assigned_contractor:
            incident.assigned_contractor.completed_repairs += 1
    elif report.outcome == VerificationOutcome.REPAIR_INCOMPLETE:
        incident.status = IncidentStatus.REWORK_REQUIRED
    else:
        incident.status = IncidentStatus.VERIFICATION_UNCERTAIN

    db.save_verification(report)

    return {
        "incident": incident,
        "verification_report": report
    }
