import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ExifTags
from fastapi import UploadFile, HTTPException

from app.core.config import REPAIRS_DIR
from app.models.schemas import (
    Incident,
    IncidentStatus,
    RepairSubmission,
    RepairSubmissionResponse,
    ContractorScorecard
)
from app.core.database import db


class ContractorService:
    """
    Core business logic for contractor work order management, EXIF metadata extraction,
    and repair evidence submission.
    """
    @staticmethod
    def extract_image_exif(image_path: Path) -> Dict[str, Any]:
        """
        Extracts EXIF metadata including camera device, capture timestamp,
        and embedded GPS coordinates if available.
        """
        metadata: Dict[str, Any] = {
            "has_exif": False,
            "has_gps": False
        }

        try:
            with Image.open(image_path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["format"] = img.format

                exif = img.getexif()
                if not exif:
                    return metadata

                metadata["has_exif"] = True
                named_tags = {}
                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    # Convert binary or non-serializable values
                    if isinstance(value, (str, int, float)):
                        named_tags[tag_name] = value

                if "Make" in named_tags:
                    metadata["camera_make"] = named_tags["Make"]
                if "Model" in named_tags:
                    metadata["camera_model"] = named_tags["Model"]
                if "DateTime" in named_tags:
                    metadata["capture_datetime"] = named_tags["DateTime"]

                # Check GPS Info sub-IFD
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    metadata["has_gps"] = True
                    metadata["gps_raw"] = str(gps_ifd)

        except Exception as e:
            metadata["error"] = str(e)

        return metadata

    @classmethod
    def process_repair_submission(
        cls,
        incident_id: str,
        contractor_id: str,
        file: UploadFile,
        latitude: float,
        longitude: float,
        accuracy_m: Optional[float] = 5.0,
        asphalt_mix_type: Optional[str] = "Hot-Mix Asphalt (HMA)",
        asphalt_used_kg: Optional[float] = None,
        engineering_notes: Optional[str] = None
    ) -> RepairSubmissionResponse:
        """
        Validates work order eligibility, saves the repair evidence photograph,
        extracts camera EXIF telemetry, transitions incident to VERIFICATION_PENDING,
        and creates a persistent RepairSubmission record.
        """
        # 1. Validate Incident Existence
        incident = db.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

        # 2. Validate Contractor Authorization
        if not incident.assigned_contractor or incident.assigned_contractor.id != contractor_id:
            assigned_id = incident.assigned_contractor.id if incident.assigned_contractor else "None"
            raise HTTPException(
                status_code=403,
                detail=f"Contractor '{contractor_id}' is not authorized for incident '{incident_id}'. Assigned contractor is '{assigned_id}'."
            )

        # 3. Validate Incident Lifecycle State
        allowed_submission_states = [
            IncidentStatus.ASSIGNED,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.REWORK_REQUIRED
        ]
        if incident.status not in allowed_submission_states:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit repair evidence for incident in state '{incident.status.value}'. Eligible states: {[s.value for s in allowed_submission_states]}."
            )

        # 4. Save Repair Evidence Image File
        now = datetime.now(timezone.utc)
        file_ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
        if file_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            file_ext = ".jpg"

        submission_id = f"SUB-2026-{uuid.uuid4().hex[:6].upper()}"
        repair_filename = f"repair_{incident_id}_{submission_id}{file_ext}"
        repair_filepath = REPAIRS_DIR / repair_filename

        try:
            with open(repair_filepath, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save evidence photograph: {str(e)}")

        # 5. Extract Camera & EXIF Telemetry
        exif_data = cls.extract_image_exif(repair_filepath)

        # 6. Create Submission Record
        submission = RepairSubmission(
            id=submission_id,
            incident_id=incident_id,
            contractor_id=contractor_id,
            submitted_at=now,
            submission_latitude=latitude,
            submission_longitude=longitude,
            submission_accuracy_m=accuracy_m,
            repair_photo_url=f"/storage/repairs/{repair_filename}",
            asphalt_mix_type=asphalt_mix_type or "Hot-Mix Asphalt (HMA)",
            asphalt_used_kg=asphalt_used_kg,
            engineering_notes=engineering_notes or "Asphalt compacted per municipal specifications.",
            exif_metadata=exif_data
        )
        db.save_repair_submission(submission)

        # 7. Transition Incident State to VERIFICATION_PENDING
        previous_status = incident.status
        audit_note = (
            f"Contractor submitted repair evidence photo ({submission_id}). "
            f"Reported Coordinates: ({latitude:.6f}, {longitude:.6f}, accuracy: {accuracy_m}m). "
            f"Asphalt Used: {asphalt_used_kg}kg ({asphalt_mix_type}). "
            f"Handed off to Phase 5 AI Verification Queue."
        )

        db.transition_status(
            incident_id=incident_id,
            new_status=IncidentStatus.VERIFICATION_PENDING,
            actor=f"Contractor Client ({contractor_id})",
            notes=audit_note
        )

        # 8. Closed-Loop AI Verification Execution
        from app.services.verification import verification_engine
        verification_report = None
        try:
            verification_report = verification_engine.verify_repair(incident, submission)
        except Exception as e:
            print(f"[ContractorService] Auto-verification warning: {e}")

        final_incident = db.get_incident(incident_id)
        current_status = final_incident.status if final_incident else IncidentStatus.VERIFICATION_PENDING
        outcome_str = verification_report.outcome.value if verification_report else "QUEUED"

        return RepairSubmissionResponse(
            submission=submission,
            incident_id=incident_id,
            previous_status=previous_status,
            new_status=current_status,
            message=f"Repair evidence processed. AI Verification Outcome: {outcome_str}.",
            verification_report=verification_report
        )

    @staticmethod
    def acknowledge_work_order(incident_id: str, contractor_id: str, notes: Optional[str] = None) -> Incident:
        """
        Contractor marks an assigned incident as IN_PROGRESS to indicate crew dispatch.
        """
        incident = db.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

        if not incident.assigned_contractor or incident.assigned_contractor.id != contractor_id:
            raise HTTPException(status_code=403, detail="Unauthorized contractor for this incident.")

        if incident.status != IncidentStatus.ASSIGNED and incident.status != IncidentStatus.REWORK_REQUIRED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot acknowledge incident currently in state '{incident.status.value}'."
            )

        updated = db.transition_status(
            incident_id=incident_id,
            new_status=IncidentStatus.IN_PROGRESS,
            actor=f"Contractor Crew ({contractor_id})",
            notes=notes or "Maintenance crew dispatched and commenced site repair."
        )
        return updated


contractor_service = ContractorService()

