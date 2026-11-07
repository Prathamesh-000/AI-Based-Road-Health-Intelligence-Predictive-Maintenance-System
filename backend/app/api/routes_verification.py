import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from fastapi.responses import FileResponse

from app.models.schemas import (
    VerificationReport,
    VerificationOutcome,
    VerifyIncidentRequest,
    IncidentStatus
)
from app.core.database import db
from app.core.config import REPAIRS_DIR, UPLOAD_DIR
from app.services.verification import verification_engine


router = APIRouter(prefix="/verify", tags=["Phase 5: Closed-Loop AI Verification & Anti-Fraud"])


@router.post("/{incident_id}", response_model=VerificationReport, summary="Trigger AI Verification on Incident")
def trigger_incident_verification(
    incident_id: str,
    request: VerifyIncidentRequest = Body(default_factory=VerifyIncidentRequest)
):
    """
    Executes automated closed-loop forensic verification on a submitted repair:
    - Haversine geofence proximity check (<= 50m)
    - Perceptual hash (pHash) duplicate & recycling fraud detection
    - Planar homography perspective alignment via ORB + RANSAC
    - Dual-head residual defect detection & fresh bitumen texture analysis
    - Automated lifecycle state machine transition (VERIFIED / REWORK_REQUIRED)
    """
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    submission = db.get_submission_by_incident(incident_id)
    if not submission:
        raise HTTPException(
            status_code=400,
            detail=f"No repair evidence has been submitted yet for incident '{incident_id}'. Submit repair evidence first."
        )

    try:
        report = verification_engine.verify_repair(
            incident=incident,
            submission=submission,
            force_override=request.force_override,
            manual_notes=request.manual_notes
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification engine failure: {str(e)}")


@router.get("/{incident_id}/report", response_model=VerificationReport, summary="Get Verification Report for Incident")
def get_incident_verification_report(incident_id: str):
    """
    Retrieves the latest AI verification report, feature alignment count,
    geofence telemetry, and visual diff URL for a specific incident.
    """
    report = db.get_verification_by_incident(incident_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No verification report found for incident '{incident_id}'."
        )
    return report


@router.get("/reports", response_model=List[VerificationReport], summary="List All Verification Reports")
def list_verification_reports(
    outcome: Optional[VerificationOutcome] = Query(None, description="Filter by verification outcome"),
    limit: int = Query(50, ge=1, le=200, description="Maximum reports to return")
):
    """
    Lists historical AI verification reports, with optional filtering by outcome:
    - REPAIR_SUCCESSFUL
    - REPAIR_INCOMPLETE
    - VERIFICATION_UNCERTAIN
    """
    reports = db.list_verification_reports(outcome=outcome)
    return reports[:limit]


@router.post("/evaluate-images", summary="Forensic Evaluation of Arbitrary Before/After Images")
def evaluate_arbitrary_images(
    before_file: UploadFile = File(..., description="Original road distress photo"),
    after_file: UploadFile = File(..., description="Repaired surface photo")
):
    """
    Performs direct forensic comparison of any two pavement images:
    computes pHash Hamming distance, ORB homography alignment, residual distress,
    and bitumen texture compliance score.
    """
    temp_id = uuid.uuid4().hex[:8]
    ext_b = Path(before_file.filename).suffix or ".jpg"
    ext_a = Path(after_file.filename).suffix or ".jpg"

    b_path = UPLOAD_DIR / f"eval_before_{temp_id}{ext_b}"
    a_path = UPLOAD_DIR / f"eval_after_{temp_id}{ext_a}"

    try:
        with open(b_path, "wb") as f_out:
            shutil.copyfileobj(before_file.file, f_out)
        with open(a_path, "wb") as f_out:
            shutil.copyfileobj(after_file.file, f_out)

        result = verification_engine.evaluate_image_pair(b_path, a_path)
        return {
            "status": "success",
            "evaluation": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image evaluation error: {str(e)}")


@router.get("/visual-diff/{incident_id}", summary="Download or View Visual Difference Audit Card")
def get_visual_diff_card(incident_id: str):
    """
    Returns the composite 3-panel audit image:
    [ Before Distress | After Repair | Perspective Diff Heatmap ]
    """
    report = db.get_verification_by_incident(incident_id)
    if not report or not report.visual_diff_url:
        raise HTTPException(
            status_code=404,
            detail=f"No visual diff audit card generated for incident '{incident_id}'."
        )

    resolved = verification_engine.resolve_image_path(report.visual_diff_url)
    if not resolved or not resolved.exists():
        raise HTTPException(status_code=404, detail="Visual difference audit card file missing on disk.")

    return FileResponse(path=str(resolved), media_type="image/jpeg", filename=resolved.name)

