from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    RoadHealthRating,
    RoadSegmentHealth,
    MunicipalRHIResponse,
    GeoJSONGeometry,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    PublicAuditCard
)
from app.core.database import db
from app.services.spatial import REGISTERED_ROAD_SEGMENTS, REGISTERED_CONTRACTORS


class CivicIntelligenceEngine:
    """
    Core Civic Intelligence & Public Transparency Service.
    Computes ASTM D6433 Pavement Condition Index (PCI / RHI),
    formats GeoJSON hazard navigation payloads, and aggregates public audit cards.
    """

    @staticmethod
    def classify_rating(score: float) -> RoadHealthRating:
        """
        Classifies numerical RHI (0 - 100) into standardized ASTM PCI condition categories.
        """
        if score >= 85.0:
            return RoadHealthRating.EXCELLENT
        elif score >= 70.0:
            return RoadHealthRating.GOOD
        elif score >= 55.0:
            return RoadHealthRating.FAIR
        elif score >= 40.0:
            return RoadHealthRating.POOR
        elif score >= 25.0:
            return RoadHealthRating.VERY_POOR
        else:
            return RoadHealthRating.FAILED

    def compute_municipal_rhi(self) -> MunicipalRHIResponse:
        """
        Computes the city-wide Road Health Index (RHI) and breakdown per road segment.
        Active/unrepaired defects incur deduct points according to ASTM D6433.
        Repaired & verified incidents restore pavement index points.
        """
        now = datetime.now(timezone.utc)
        all_incidents = list(db.incidents.values())

        active_statuses = {
            IncidentStatus.REPORTED,
            IncidentStatus.ASSIGNED,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.REWORK_REQUIRED,
            IncidentStatus.VERIFICATION_PENDING
        }
        remediation_statuses = {
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.REWORK_REQUIRED,
            IncidentStatus.VERIFICATION_PENDING
        }
        completed_statuses = {
            IncidentStatus.VERIFIED,
            IncidentStatus.CLOSED
        }

        # 1. Segment-by-Segment Computation
        segment_breakdowns: List[RoadSegmentHealth] = []
        weighted_rhi_sum = 0.0
        total_road_network_km = 0.0

        for seg in REGISTERED_ROAD_SEGMENTS:
            seg_incidents = [i for i in all_incidents if i.road_segment.segment_id == seg.segment_id]
            seg_active = [i for i in seg_incidents if i.status in active_statuses]
            seg_verified = [i for i in seg_incidents if i.status in completed_statuses]

            total_deduct = sum(i.pci_deduct_points for i in seg_active)
            segment_rhi = max(0.0, min(100.0, 100.0 - total_deduct))
            rating = self.classify_rating(segment_rhi)

            contractor = REGISTERED_CONTRACTORS.get(seg.contractor_id)
            contractor_name = contractor.name if contractor else "Municipal Highway Works"

            seg_health = RoadSegmentHealth(
                segment_id=seg.segment_id,
                name=seg.name,
                zone=seg.zone,
                contractor_id=seg.contractor_id,
                contractor_name=contractor_name,
                total_length_km=seg.total_length_km,
                active_defects_count=len(seg_active),
                verified_repairs_count=len(seg_verified),
                total_pci_deduct=round(total_deduct, 1),
                rhi_score=round(segment_rhi, 1),
                health_rating=rating
            )
            segment_breakdowns.append(seg_health)

            weighted_rhi_sum += (segment_rhi * seg.total_length_km)
            total_road_network_km += seg.total_length_km

        # 2. Overall City-Wide RHI
        if total_road_network_km > 0:
            overall_rhi = round(weighted_rhi_sum / total_road_network_km, 1)
        else:
            overall_rhi = 100.0

        city_rating = self.classify_rating(overall_rhi)

        # 3. Aggregate City Metrics
        active_hazards = sum(1 for i in all_incidents if i.status in active_statuses)
        in_remediation = sum(1 for i in all_incidents if i.status in remediation_statuses)
        verified_count = sum(1 for i in all_incidents if i.status in completed_statuses)
        repaired_pci_restored = round(sum(i.pci_deduct_points for i in all_incidents if i.status in completed_statuses), 1)

        # Asphalt Laid (from repair submissions or physical metrics of completed repairs)
        total_asphalt_kg = sum(
            sub.asphalt_used_kg or 0.0
            for sub in db.repair_submissions.values()
        )
        if total_asphalt_kg == 0.0:
            total_asphalt_kg = sum(
                i.physical_metrics.asphalt_required_kg
                for i in all_incidents if i.status in completed_statuses
            )

        return MunicipalRHIResponse(
            city_name="Metro Municipal Road Network",
            overall_rhi_score=overall_rhi,
            health_rating=city_rating,
            total_incidents_logged=len(all_incidents),
            active_hazards_count=active_hazards,
            in_remediation_count=in_remediation,
            verified_repairs_count=verified_count,
            repaired_pci_restored=repaired_pci_restored,
            asphalt_laid_kg=round(total_asphalt_kg, 1),
            evaluated_at=now,
            segment_breakdown=segment_breakdowns
        )

    def generate_hazard_geojson(self) -> GeoJSONFeatureCollection:
        """
        Builds RFC 7946 compliant GeoJSON FeatureCollection of all active road hazards.
        Optimized for third-party navigation apps (Waze, OpenStreetMap, Google Maps).
        """
        active_statuses = {
            IncidentStatus.REPORTED,
            IncidentStatus.ASSIGNED,
            IncidentStatus.IN_PROGRESS,
            IncidentStatus.REWORK_REQUIRED,
            IncidentStatus.VERIFICATION_PENDING
        }

        severity_weights = {
            SeverityLevel.CRITICAL: 5,
            SeverityLevel.HIGH: 4,
            SeverityLevel.MEDIUM: 3,
            SeverityLevel.LOW: 2
        }

        features: List[GeoJSONFeature] = []

        for inc in db.incidents.values():
            if inc.status not in active_statuses:
                continue

            contractor_name = inc.assigned_contractor.name if inc.assigned_contractor else "Unassigned"
            hazard_level = severity_weights.get(inc.severity, 3)

            feature = GeoJSONFeature(
                type="Feature",
                geometry=GeoJSONGeometry(
                    type="Point",
                    coordinates=[inc.location.longitude, inc.location.latitude]
                ),
                properties={
                    "incident_id": inc.id,
                    "defect_type": inc.defect_type.value,
                    "severity": inc.severity.value,
                    "status": inc.status.value,
                    "hazard_level": hazard_level,
                    "road_name": inc.road_segment.name,
                    "zone": inc.road_segment.zone,
                    "contractor": contractor_name,
                    "pci_deduct": inc.pci_deduct_points,
                    "surface_area_m2": inc.physical_metrics.surface_area_m2,
                    "asphalt_required_kg": inc.physical_metrics.asphalt_required_kg,
                    "evidence_image_url": inc.evidence_image_url,
                    "sla_status": inc.sla_metrics.status.value,
                    "remaining_hours": inc.sla_metrics.remaining_hours,
                    "reported_at": inc.created_at.isoformat()
                }
            )
            features.append(feature)

        return GeoJSONFeatureCollection(
            type="FeatureCollection",
            features=features
        )

    def get_public_audit_feed(self, limit: int = 50) -> List[PublicAuditCard]:
        """
        Builds public audit cards for all incidents with submitted repairs or completed verifications.
        Provides transparent before/after verification evidence to citizens and civic auditors.
        """
        cards: List[PublicAuditCard] = []

        for inc in db.incidents.values():
            sub = db.get_submission_by_incident(inc.id)
            report = db.get_verification_by_incident(inc.id)

            contractor_name = inc.assigned_contractor.name if inc.assigned_contractor else "Municipal Highway Works"
            verified_at = report.evaluated_at if report else (sub.submitted_at if sub else None)

            card = PublicAuditCard(
                incident_id=inc.id,
                defect_type=inc.defect_type,
                severity=inc.severity,
                status=inc.status,
                road_name=inc.road_segment.name,
                zone=inc.road_segment.zone,
                contractor_name=contractor_name,
                latitude=inc.location.latitude,
                longitude=inc.location.longitude,
                reported_at=inc.created_at,
                verified_at=verified_at,
                evidence_image_url=inc.evidence_image_url,
                repair_photo_url=sub.repair_photo_url if sub else None,
                visual_diff_url=report.visual_diff_url if report else None,
                confidence_score=report.confidence_score if report else None,
                feature_matches_count=report.feature_matches_count if report else None,
                texture_compliance_score=report.patch_texture_score if report else None,
                explanation=report.explanation if report else None,
                asphalt_used_kg=sub.asphalt_used_kg if sub else None
            )
            cards.append(card)

        # Sort so verified and verified-pending incidents appear first, then newest
        cards.sort(
            key=lambda c: (
                1 if c.status in [IncidentStatus.VERIFIED, IncidentStatus.CLOSED] else (2 if c.visual_diff_url else 3),
                -c.reported_at.timestamp()
            )
        )
        return cards[:limit]

    def get_incident_audit_card(self, incident_id: str) -> Optional[PublicAuditCard]:
        """
        Returns full public audit card for an individual incident.
        """
        inc = db.get_incident(incident_id)
        if not inc:
            return None

        sub = db.get_submission_by_incident(inc.id)
        report = db.get_verification_by_incident(inc.id)
        contractor_name = inc.assigned_contractor.name if inc.assigned_contractor else "Municipal Highway Works"
        verified_at = report.evaluated_at if report else (sub.submitted_at if sub else None)

        return PublicAuditCard(
            incident_id=inc.id,
            defect_type=inc.defect_type,
            severity=inc.severity,
            status=inc.status,
            road_name=inc.road_segment.name,
            zone=inc.road_segment.zone,
            contractor_name=contractor_name,
            latitude=inc.location.latitude,
            longitude=inc.location.longitude,
            reported_at=inc.created_at,
            verified_at=verified_at,
            evidence_image_url=inc.evidence_image_url,
            repair_photo_url=sub.repair_photo_url if sub else None,
            visual_diff_url=report.visual_diff_url if report else None,
            confidence_score=report.confidence_score if report else None,
            feature_matches_count=report.feature_matches_count if report else None,
            texture_compliance_score=report.patch_texture_score if report else None,
            explanation=report.explanation if report else None,
            asphalt_used_kg=sub.asphalt_used_kg if sub else None
        )


civic_engine = CivicIntelligenceEngine()

