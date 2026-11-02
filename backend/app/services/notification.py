import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict

from app.core.config import (
    SMTP_ENABLED,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    NOTIFICATION_COOLING_HOURS,
    DUPLICATE_DISTANCE_THRESHOLD_M
)
from app.models.schemas import (
    Incident,
    Contractor,
    NotificationLog,
    NotificationEvent,
    NotificationChannel,
    NotificationStatus,
    SeverityLevel,
    AuditLogEntry
)
from app.services.spatial import GeospatialMatcher


class NotificationTemplateRenderer:
    """
    Renders responsive, professional HTML and plaintext email templates
    for municipal contractor dispatch.
    """
    @staticmethod
    def get_severity_color(severity: SeverityLevel) -> Tuple[str, str]:
        # returns (bg_color, border_color)
        if severity == SeverityLevel.CRITICAL:
            return "#EF4444", "#DC2626"
        elif severity == SeverityLevel.HIGH:
            return "#F97316", "#EA580C"
        elif severity == SeverityLevel.MEDIUM:
            return "#F59E0B", "#D97706"
        else:
            return "#10B981", "#059669"

    @classmethod
    def render_html(
        cls,
        incident: Incident,
        event: NotificationEvent,
        custom_notes: Optional[str] = None
    ) -> str:
        color, border_color = cls.get_severity_color(incident.severity)
        contractor_name = incident.assigned_contractor.name if incident.assigned_contractor else "Contractor Unassigned"
        contractor_company = incident.assigned_contractor.company if incident.assigned_contractor else ""
        maps_link = f"https://maps.google.com/?q={incident.location.latitude},{incident.location.longitude}"
        created_str = incident.created_at.strftime("%Y-%m-%d %H:%M UTC")
        deadline_str = incident.sla_metrics.deadline.strftime("%Y-%m-%d %H:%M UTC")

        event_title = {
            NotificationEvent.INCIDENT_ASSIGNED: "NEW MAINTENANCE WORK ORDER DISPATCH",
            NotificationEvent.SLA_REMINDER: "URGENT SLA DEADLINE REMINDER",
            NotificationEvent.SLA_BREACHED: "CRITICAL: SLA DEADLINE BREACH NOTIFICATION",
            NotificationEvent.REWORK_REQUIRED: "REPAIR REWORK REQUIRED - DEFECT RESIDUAL DETECTED",
            NotificationEvent.REPAIR_VERIFIED: "MAINTENANCE REPAIR VERIFIED SUCCESSFUL"
        }.get(event, "ROAD MAINTENANCE NOTIFICATION")

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_title}</title>
</head>
<body style="margin:0; padding:0; background-color:#0b0f19; font-family:'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#0b0f19; padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="max-width:620px; width:100%; background-color:#131b2e; border:1px solid #1e293b; border-radius:12px; overflow:hidden; box-shadow:0 10px 25px rgba(0,0,0,0.5);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background:linear-gradient(90deg, #d97706, #4f46e5); padding:3px 0 0 0;"></td>
          </tr>
          <tr>
            <td style="padding:28px 32px 20px 32px; border-bottom:1px solid #1e293b;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <span style="font-size:11px; font-weight:700; color:#f59e0b; text-transform:uppercase; letter-spacing:1.5px; display:block; margin-bottom:4px;">Municipal Infrastructure Intelligence</span>
                    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff; letter-spacing:-0.5px;">RoadSentinel AI</h1>
                  </td>
                  <td align="right" valign="top">
                    <span style="display:inline-block; background-color:{color}; color:#ffffff; font-size:11px; font-weight:800; padding:4px 10px; border-radius:6px; text-transform:uppercase; letter-spacing:0.5px;">
                      {incident.severity.value} SEVERITY
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Event Notice Bar -->
          <tr>
            <td style="padding:16px 32px; background-color:#1a233a; border-bottom:1px solid #1e293b;">
              <span style="font-size:12px; font-weight:700; color:#93c5fd; text-transform:uppercase; letter-spacing:0.5px;">Notification:</span>
              <strong style="font-size:14px; color:#ffffff; display:block; margin-top:2px;">{event_title}</strong>
              <span style="font-size:12px; color:#94a3b8; display:block; margin-top:2px;">Work Order Reference: <strong style="color:#f1f5f9; font-family:monospace;">{incident.id}</strong></span>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding:28px 32px;">
              <p style="margin:0 0 18px 0; font-size:14px; line-height:1.6; color:#cbd5e1;">
                Attn: <strong>{contractor_name}</strong> ({contractor_company})<br>
                A qualifying road distress incident has been detected and automatically assigned to your organization under your active maintenance jurisdiction contract.
              </p>

              <!-- Distress Details Card -->
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#0b1120; border:1px solid #1e293b; border-radius:8px; margin-bottom:20px;">
                <tr>
                  <td style="padding:16px 20px;">
                    <table width="100%" cellspacing="0" cellpadding="6" border="0" style="font-size:13px;">
                      <tr>
                        <td width="38%" style="color:#94a3b8; font-weight:600;">Defect Category:</td>
                        <td style="color:#ffffff; font-weight:700; text-transform:uppercase;">{incident.defect_type.value.replace('_', ' ')}</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8; font-weight:600;">Road Segment:</td>
                        <td style="color:#ffffff;">{incident.road_segment.name} ({incident.road_segment.zone})</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8; font-weight:600;">GPS Coordinates:</td>
                        <td style="color:#ffffff;">
                          <a href="{maps_link}" target="_blank" style="color:#38bdf8; text-decoration:none; font-family:monospace; font-weight:600;">
                            {incident.location.latitude:.6f}, {incident.location.longitude:.6f} &#8599; View on Map
                          </a>
                        </td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8; font-weight:600;">Reported Timestamp:</td>
                        <td style="color:#cbd5e1;">{created_str}</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8; font-weight:600;">SLA Repair Window:</td>
                        <td style="color:#f59e0b; font-weight:700;">{incident.sla_metrics.allowed_hours} Hours</td>
                      </tr>
                      <tr>
                        <td style="color:#94a3b8; font-weight:600;">Hard SLA Deadline:</td>
                        <td style="color:#ef4444; font-weight:700;">{deadline_str}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Physical Quantification Box -->
              <div style="background-color:#1e1b4b; border:1px solid #3730a3; border-radius:8px; padding:16px 20px; margin-bottom:24px;">
                <span style="font-size:11px; font-weight:700; color:#a5b4fc; text-transform:uppercase; letter-spacing:1px; display:block; margin-bottom:6px;">Civil Procurement & Volume Quantification</span>
                <table width="100%" cellspacing="0" cellpadding="4" border="0" style="font-size:13px; color:#e0e7ff;">
                  <tr>
                    <td width="50%">Estimated Defect Depth: <strong>{incident.physical_metrics.estimated_depth_m * 100:.1f} cm</strong></td>
                    <td width="50%">Displacement Volume: <strong>{incident.physical_metrics.volume_m3:.4f} m&#179;</strong></td>
                  </tr>
                  <tr>
                    <td colspan="2" style="padding-top:6px; font-size:14px; color:#38bdf8;">
                      Compacted Hot-Mix Asphalt Required: <strong style="font-size:16px; color:#ffffff;">{incident.physical_metrics.asphalt_required_kg:.1f} kg</strong>
                    </td>
                  </tr>
                </table>
              </div>

              <!-- Evidence Crop -->
              <div style="margin-bottom:24px;">
                <span style="font-size:12px; font-weight:600; color:#94a3b8; display:block; margin-bottom:8px;">Optical Video Evidence Crop:</span>
                <div style="background-color:#0b1120; border:1px solid #1e293b; border-radius:8px; padding:10px; text-align:center;">
                  <span style="font-size:12px; font-family:monospace; color:#64748b;">Evidence Path: {incident.evidence_image_url}</span>
                </div>
              </div>

              {f'<div style="background-color:#262626; border-left:4px solid #f59e0b; padding:12px 16px; margin-bottom:24px; font-size:13px; color:#cbd5e1;"><strong>Note:</strong> {custom_notes}</div>' if custom_notes else ''}

              <!-- Action Instructions -->
              <div style="background-color:#0b1120; border-left:4px solid #38bdf8; padding:14px 18px; margin-bottom:28px;">
                <h4 style="margin:0 0 6px 0; font-size:13px; color:#ffffff;">Contractor Action Required:</h4>
                <ol style="margin:0; padding-left:18px; font-size:12px; line-height:1.6; color:#94a3b8;">
                  <li>Dispatch maintenance repair crew with necessary materials to the specified coordinates.</li>
                  <li>Perform cold-milling and asphalt compaction following municipal road standards.</li>
                  <li>Capture a high-resolution "After" repair photo from the site (GPS geofenced &le;50m).</li>
                  <li>Submit completion evidence via the Contractor Web Portal for closed-loop AI verification.</li>
                </ol>
              </div>

              <!-- CTA Button -->
              <table width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center">
                    <a href="{maps_link}" target="_blank" style="display:inline-block; background-color:#d97706; color:#ffffff; font-size:13px; font-weight:700; text-decoration:none; padding:12px 28px; border-radius:8px; box-shadow:0 4px 12px rgba(217,119,6,0.3);">
                      Navigate to Defect Location &#8594;
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px; background-color:#0b0f19; border-top:1px solid #1e293b; text-align:center; font-size:11px; color:#64748b; line-height:1.5;">
              This is an automated dispatch from <strong>RoadSentinel AI Municipal Platform</strong>.<br>
              ASTM D6433 Pavement Distress Compliance &bull; Contract Assigned: {contractor_name}<br>
              Direct questions to Municipal Works Department &bull; Dispatch ID: {incident.id}
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    @classmethod
    def render_plain_text(
        cls,
        incident: Incident,
        event: NotificationEvent,
        custom_notes: Optional[str] = None
    ) -> str:
        contractor_name = incident.assigned_contractor.name if incident.assigned_contractor else "Contractor Unassigned"
        maps_link = f"https://maps.google.com/?q={incident.location.latitude},{incident.location.longitude}"
        deadline_str = incident.sla_metrics.deadline.strftime("%Y-%m-%d %H:%M UTC")

        text = f"""====================================================
ROADSENTINEL AI: WORK ORDER NOTIFICATION ({event.value})
====================================================
Work Order ID:    {incident.id}
Severity Level:   {incident.severity.value}
Defect Category:  {incident.defect_type.value.upper()}
Assigned To:      {contractor_name}
Road Segment:     {incident.road_segment.name} ({incident.road_segment.zone})
GPS Coordinates:  {incident.location.latitude:.6f}, {incident.location.longitude:.6f}
Google Maps:      {maps_link}
SLA Window:       {incident.sla_metrics.allowed_hours} Hours
Hard Deadline:    {deadline_str}

QUANTIFICATION:
- Depth:          {incident.physical_metrics.estimated_depth_m * 100:.1f} cm
- Volume:         {incident.physical_metrics.volume_m3:.4f} m3
- Asphalt Req:    {incident.physical_metrics.asphalt_required_kg:.1f} kg
- Evidence URL:   {incident.evidence_image_url}
"""
        if custom_notes:
            text += f"\nNOTES: {custom_notes}\n"

        text += """
ACTION REQUIRED:
1. Dispatch repair crew to coordinates.
2. Compact hot-mix asphalt per municipal standard.
3. Submit photo evidence through Contractor Portal for AI verification.
===================================================="""
        return text


class NotificationSuppressionEngine:
    """
    Evaluates cooling periods and spatial-temporal proximity to prevent
    contractor alert fatigue and notification spam.
    """
    @staticmethod
    def check_suppression(
        incident: Incident,
        event: NotificationEvent,
        existing_notifications: List[NotificationLog],
        active_incidents: List[Incident],
        force_resend: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a notification should be suppressed.
        Returns: (is_suppressed, reason)
        """
        if force_resend:
            return False, None

        if not incident.assigned_contractor or not incident.assigned_contractor.email:
            return True, "Suppressed: No verified contractor email address on record for this incident."

        now = datetime.now(timezone.utc)

        # Rule 1: Deduplication on exact same incident within cooling window (24h)
        for notif in existing_notifications:
            if notif.incident_id == incident.id and notif.event == event and notif.status == NotificationStatus.SENT:
                hours_since = (now - notif.created_at).total_seconds() / 3600.0
                if hours_since < 24.0:
                    return True, f"Suppressed: Duplicate alert. Notification for incident {incident.id} ({event.value}) was already dispatched {hours_since:.1f}h ago."

        # Rule 2: Spatial Proximity Suppression (Nearby Unrepaired Defect within cooling period)
        # Prevents sending 5 separate contractor emails for 5 potholes clustered on the same 50m road block
        for other in active_incidents:
            if other.id == incident.id:
                continue

            # Check if assigned to same contractor
            if (
                other.assigned_contractor and
                incident.assigned_contractor and
                other.assigned_contractor.id == incident.assigned_contractor.id
            ):
                dist_m = GeospatialMatcher.haversine_distance_m(
                    incident.location.latitude, incident.location.longitude,
                    other.location.latitude, other.location.longitude
                )

                if dist_m <= DUPLICATE_DISTANCE_THRESHOLD_M:
                    # Check if a notification was dispatched for the nearby incident recently
                    for notif in existing_notifications:
                        if notif.incident_id == other.id and notif.status == NotificationStatus.SENT:
                            hours_ago = (now - notif.created_at).total_seconds() / 3600.0
                            if hours_ago <= NOTIFICATION_COOLING_HOURS:
                                return True, (
                                    f"Suppressed: Notification cooling active. A work order was already dispatched to {incident.assigned_contractor.name} "
                                    f"for nearby defect {other.id} within {dist_m:.1f}m on {incident.road_segment.name} ({hours_ago:.1f}h ago)."
                                )

        return False, None


class NotificationDispatcher:
    """
    Core Dispatch Engine managing SMTP delivery, template compilation,
    suppression checks, and delivery tracking.
    """
    def __init__(self):
        self.template_renderer = NotificationTemplateRenderer()
        self.suppression_engine = NotificationSuppressionEngine()

    def _deliver_email_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_text: str
    ) -> Tuple[bool, str]:
        """
        Attempts SMTP transmission if enabled, or executes simulated safe delivery.
        """
        if not SMTP_ENABLED:
            # Simulated safe delivery for local development & automated test suites
            return True, f"Simulated SMTP delivery successful to {to_email} (Test Mode)"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg["To"] = to_email

            part1 = MIMEText(plain_text, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())

            return True, f"SMTP delivery confirmed by {SMTP_HOST}:{SMTP_PORT}"
        except Exception as e:
            return False, f"SMTP transmission failed: {str(e)}"

    def dispatch_incident_notification(
        self,
        incident: Incident,
        event: NotificationEvent = NotificationEvent.INCIDENT_ASSIGNED,
        channel: NotificationChannel = NotificationChannel.EMAIL,
        custom_notes: Optional[str] = None,
        force_resend: bool = False
    ) -> NotificationLog:
        """
        Executes end-to-end dispatch workflow:
        1. Evaluates suppression rules.
        2. Compiles HTML & Plaintext templates.
        3. Delivers payload via configured channel.
        4. Logs delivery attempt and updates incident audit trail.
        """
        from app.core.database import db

        now = datetime.now(timezone.utc)
        notif_id = f"NOTIF-2026-{uuid.uuid4().hex[:6].upper()}"

        contractor_id = incident.assigned_contractor.id if incident.assigned_contractor else "UNKNOWN"
        recipient_email = incident.assigned_contractor.email if incident.assigned_contractor else "none@domain.local"

        subject = f"[RoadSentinel AI] {event.value}: {incident.defect_type.value.upper()} on {incident.road_segment.name} ({incident.severity.value} Priority)"

        # 1. Check Suppression Rules
        existing_notifs = db.list_notifications()
        active_incidents = db.list_incidents()
        is_suppressed, suppression_reason = self.suppression_engine.check_suppression(
            incident=incident,
            event=event,
            existing_notifications=existing_notifs,
            active_incidents=active_incidents,
            force_resend=force_resend
        )

        html_content = self.template_renderer.render_html(incident, event, custom_notes)
        plain_text = self.template_renderer.render_plain_text(incident, event, custom_notes)

        if is_suppressed:
            log = NotificationLog(
                id=notif_id,
                incident_id=incident.id,
                contractor_id=contractor_id,
                recipient_email=recipient_email,
                event=event,
                channel=channel,
                status=NotificationStatus.SUPPRESSED,
                subject=subject,
                html_content=html_content,
                plain_text=plain_text,
                created_at=now,
                sent_at=None,
                suppression_reason=suppression_reason,
                attempt_count=0,
                delivery_response="Suppressed by Anti-Spam Engine"
            )
            db.save_notification(log)

            incident.audit_trail.append(AuditLogEntry(
                timestamp=now,
                previous_status=incident.status,
                new_status=incident.status,
                actor="Notification Suppression Engine",
                notes=suppression_reason
            ))

            return log

        # 2. Deliver Notification
        success, response_msg = self._deliver_email_smtp(
            to_email=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_text=plain_text
        )

        status = NotificationStatus.SENT if success else NotificationStatus.FAILED

        log = NotificationLog(
            id=notif_id,
            incident_id=incident.id,
            contractor_id=contractor_id,
            recipient_email=recipient_email,
            event=event,
            channel=channel,
            status=status,
            subject=subject,
            html_content=html_content,
            plain_text=plain_text,
            created_at=now,
            sent_at=now if success else None,
            suppression_reason=None,
            attempt_count=1,
            delivery_response=response_msg
        )
        db.save_notification(log)

        # 3. Update Incident Audit Trail
        audit_note = f"Automated {event.value} dispatch {status.value.lower()} to {recipient_email} (ID: {notif_id})"
        incident.audit_trail.append(AuditLogEntry(
            timestamp=now,
            previous_status=incident.status,
            new_status=incident.status,
            actor="Notification Dispatch Engine",
            notes=audit_note
        ))

        return log


# Global Singleton Dispatcher Instance
notification_dispatcher = NotificationDispatcher()

