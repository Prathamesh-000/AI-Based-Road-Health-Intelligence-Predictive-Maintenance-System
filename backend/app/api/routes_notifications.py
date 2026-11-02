from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import HTMLResponse
from typing import List, Optional

from app.models.schemas import (
    NotificationLog,
    NotificationStatus,
    NotificationEvent,
    NotificationChannel,
    DispatchIncidentRequest
)
from app.core.database import db
from app.services.notification import notification_dispatcher, NotificationTemplateRenderer

router = APIRouter(prefix="/notifications", tags=["Phase 3: Automated Contractor Notification & Dispatch"])


@router.get("", response_model=List[NotificationLog])
async def list_notifications(
    incident_id: Optional[str] = Query(None, description="Filter by incident ID"),
    contractor_id: Optional[str] = Query(None, description="Filter by contractor ID"),
    status: Optional[NotificationStatus] = Query(None, description="Filter by status (SENT, SUPPRESSED, FAILED)"),
    event: Optional[NotificationEvent] = Query(None, description="Filter by event type")
):
    """
    Retrieves all dispatch notification audit logs with multi-attribute filtering.
    """
    return db.list_notifications(
        incident_id=incident_id,
        contractor_id=contractor_id,
        status=status,
        event=event
    )


@router.get("/{notification_id}", response_model=NotificationLog)
async def get_notification(notification_id: str):
    """
    Retrieves full details of a specific notification dispatch record.
    """
    notif = db.get_notification(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification '{notification_id}' not found.")
    return notif


@router.get("/preview/{incident_id}", response_class=HTMLResponse)
async def preview_incident_notification_html(
    incident_id: str,
    event: NotificationEvent = Query(NotificationEvent.INCIDENT_ASSIGNED, description="Event type to preview"),
    notes: Optional[str] = Query(None, description="Optional custom notes to include")
):
    """
    Renders and previews the exact HTML dispatch email that will be transmitted to the contractor.
    """
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    html = NotificationTemplateRenderer.render_html(
        incident=incident,
        event=event,
        custom_notes=notes
    )
    return HTMLResponse(content=html)


@router.post("/dispatch/{incident_id}", response_model=NotificationLog, status_code=status.HTTP_200_OK)
async def dispatch_notification(
    incident_id: str,
    request: DispatchIncidentRequest,
    background_tasks: BackgroundTasks
):
    """
    Triggers an automated dispatch event for an existing incident ticket.
    Evaluates anti-spam suppression rules unless 'force_resend' is specified.
    """
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    # Execute dispatch
    log = notification_dispatcher.dispatch_incident_notification(
        incident=incident,
        event=request.event,
        channel=request.channel,
        custom_notes=request.custom_notes,
        force_resend=request.force_resend
    )

    return log

