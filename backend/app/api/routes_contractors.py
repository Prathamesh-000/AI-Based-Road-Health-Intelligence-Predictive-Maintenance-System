from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, status
from typing import List, Optional

from app.models.schemas import (
    Contractor,
    ContractorScorecard,
    Incident,
    IncidentStatus,
    SeverityLevel,
    RepairSubmission,
    RepairSubmissionResponse,
    AcknowledgeIncidentRequest
)
from app.core.database import db
from app.services.spatial import GeospatialMatcher
from app.services.contractor import contractor_service

router = APIRouter(prefix="/contractors", tags=["Phase 4: Contractor Dashboard & Evidence Submission"])
spatial_matcher = GeospatialMatcher()


@router.get("", response_model=List[ContractorScorecard])
async def list_all_contractor_scorecards():
    """
    Retrieves performance scorecards and live maintenance workloads for all registered contractors.
    """
    contractors = spatial_matcher.list_all_contractors()
    scorecards = []
    for c in contractors:
        scorecard = db.get_contractor_scorecard(c.id)
        if scorecard:
            scorecards.append(scorecard)
    return scorecards


@router.get("/{contractor_id}", response_model=ContractorScorecard)
async def get_contractor_details(contractor_id: str):
    """
    Retrieves full profile, operational metrics, and performance scorecard for a specific contractor.
    """
    scorecard = db.get_contractor_scorecard(contractor_id)
    if not scorecard:
        raise HTTPException(status_code=404, detail=f"Contractor '{contractor_id}' not found.")
    return scorecard


@router.get("/{contractor_id}/queue", response_model=List[Incident])
async def get_contractor_work_queue(
    contractor_id: str,
    status: Optional[IncidentStatus] = Query(None, description="Filter queue by lifecycle status"),
    severity: Optional[SeverityLevel] = Query(None, description="Filter queue by severity"),
    overdue_only: bool = Query(False, description="Filter only work orders breaching SLA")
):
    """
    Retrieves the assigned work order queue for a contractor with SLA urgency and status filters.
    """
    scorecard = db.get_contractor_scorecard(contractor_id)
    if not scorecard:
        raise HTTPException(status_code=404, detail=f"Contractor '{contractor_id}' not found.")

    incidents = db.list_incidents(
        contractor_id=contractor_id,
        status=status,
        severity=severity
    )

    if overdue_only:
        incidents = [i for i in incidents if i.sla_metrics.remaining_hours < 0]

    return incidents


@router.post("/{contractor_id}/acknowledge/{incident_id}", response_model=Incident)
async def acknowledge_work_order(
    contractor_id: str,
    incident_id: str,
    request: AcknowledgeIncidentRequest = AcknowledgeIncidentRequest()
):
    """
    Contractor crew acknowledges dispatch and transitions work order to IN_PROGRESS.
    """
    return contractor_service.acknowledge_work_order(
        incident_id=incident_id,
        contractor_id=contractor_id,
        notes=request.notes
    )


@router.post("/submit-repair", response_model=RepairSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_repair_evidence(
    incident_id: str = Form(..., description="Target incident reference ID"),
    contractor_id: str = Form(..., description="Submitting contractor organization ID"),
    latitude: float = Form(..., description="Contractor device latitude at site"),
    longitude: float = Form(..., description="Contractor device longitude at site"),
    accuracy_m: Optional[float] = Form(5.0, description="Device GPS accuracy in meters"),
    asphalt_mix_type: Optional[str] = Form("Hot-Mix Asphalt (HMA)", description="Asphalt compaction mix grade"),
    asphalt_used_kg: Optional[float] = Form(None, description="Actual asphalt mass utilized in kg"),
    engineering_notes: Optional[str] = Form(None, description="Contractor maintenance engineering notes"),
    repair_photo: UploadFile = File(..., description="Completed repair after-photograph")
):
    """
    Contractor submits completed repair evidence photo with GPS telemetry and compaction notes.
    Transitions ticket to VERIFICATION_PENDING and queues for automated AI inspection.
    """
    return contractor_service.process_repair_submission(
        incident_id=incident_id,
        contractor_id=contractor_id,
        file=repair_photo,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
        asphalt_mix_type=asphalt_mix_type,
        asphalt_used_kg=asphalt_used_kg,
        engineering_notes=engineering_notes
    )


@router.get("/{contractor_id}/submissions", response_model=List[RepairSubmission])
async def list_contractor_submissions(contractor_id: str):
    """
    Lists all repair evidence submissions filed by a contractor organization.
    """
    return db.list_repair_submissions(contractor_id=contractor_id)


@router.get("/submissions/{submission_id}", response_model=RepairSubmission)
async def get_repair_submission(submission_id: str):
    """
    Retrieves full details of a specific repair evidence submission record.
    """
    sub = db.get_repair_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission '{submission_id}' not found.")
    return sub

