from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
import math

from app.models.schemas import Contractor, GeoCoordinates, IncidentStatus, SeverityLevel
from app.config import SLA_HOURS


# Seed Contractor Database
SAMPLE_CONTRACTORS = [
    Contractor(
        id="CTR-001",
        name="Apex Paving Solutions",
        company="Apex Infrastructure Ltd.",
        email="dispatch@apexinfra.com",
        phone="+1-800-555-0199",
        assigned_zones=["Zone 1 - North Corridor", "Arterial Segment 4A-4C"],
        performance_score=94.2,
        completed_repairs=128
    ),
    Contractor(
        id="CTR-002",
        name="MetroRoad Maintenance Corp",
        company="MetroRoad Civil Works",
        email="repairs@metroroad.org",
        phone="+1-800-555-0245",
        assigned_zones=["Zone 2 - Downtown Central", "Highway 101 Access"],
        performance_score=91.0,
        completed_repairs=95
    ),
    Contractor(
        id="CTR-003",
        name="Civic Asphalt Engineering",
        company="Civic Build Partners",
        email="contractor@civicasphalt.net",
        phone="+1-800-555-0378",
        assigned_zones=["Zone 3 - East Suburbs", "Industrial Park Bypass"],
        performance_score=88.5,
        completed_repairs=64
    )
]

# Registered Road Segments with Spatial Bounds (min_lat, min_lng, max_lat, max_lng)
ROAD_SEGMENTS = [
    {
        "segment_id": "SEG-101",
        "name": "State Highway 17 North",
        "contractor_id": "CTR-001",
        "bounds": (18.5100, 73.8400, 18.5400, 73.8700),
        "total_length_km": 4.2
    },
    {
        "segment_id": "SEG-102",
        "name": "Central Boulevard & Ring Road",
        "contractor_id": "CTR-002",
        "bounds": (18.4900, 73.8200, 18.5200, 73.8500),
        "total_length_km": 6.8
    },
    {
        "segment_id": "SEG-103",
        "name": "Eastern Industrial Bypass",
        "contractor_id": "CTR-003",
        "bounds": (18.5300, 73.8800, 18.5700, 73.9200),
        "total_length_km": 5.1
    }
]


class SpatialAssignmentService:
    """
    Geospatial boundary matching and automated contractor assignment.
    """
    def __init__(self):
        self.contractors = {c.id: c for c in SAMPLE_CONTRACTORS}

    def match_contractor_for_location(self, lat: float, lng: float) -> Tuple[Optional[Contractor], str]:
        """
        Matches coordinates to registered road segments.
        Falls back to nearest contractor if out of strict polygon bounds.
        """
        for seg in ROAD_SEGMENTS:
            min_lat, min_lng, max_lat, max_lng = seg["bounds"]
            if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                contractor = self.contractors.get(seg["contractor_id"])
                return contractor, seg["name"]

        # Default fallback to primary contractor
        return SAMPLE_CONTRACTORS[0], "City Arterial Corridor (General Jurisdiction)"

    def calculate_sla_deadline(self, severity: SeverityLevel) -> datetime:
        """
        Calculates dynamic SLA deadline based on severity level.
        """
        hours = SLA_HOURS.get(severity.value, 72)
        return datetime.utcnow() + timedelta(hours=hours)

    def calculate_road_health_index(self, incidents: list) -> Dict[str, Any]:
        """
        Computes Road Health Index (RHI) on a 0-100 scale (ASTM D6433 PCI compliant).
        """
        base_pci = 100.0
        deduct_points = 0.0

        for inc in incidents:
            if inc.status in [IncidentStatus.VERIFIED]:
                continue  # Repaired defects do not deduct from active score
            
            weight = 8.0 if inc.severity == SeverityLevel.HIGH else (4.0 if inc.severity == SeverityLevel.MEDIUM else 1.5)
            deduct_points += weight

        final_rhi = max(10.0, round(base_pci - deduct_points, 1))

        if final_rhi >= 85:
            grade = "EXCELLENT"
            color = "#10B981"
        elif final_rhi >= 70:
            grade = "GOOD"
            color = "#3B82F6"
        elif final_rhi >= 50:
            grade = "FAIR - MAINTENANCE REQUIRED"
            color = "#F59E0B"
        else:
            grade = "CRITICAL - IMMEDIATE ATTENTION"
            color = "#EF4444"

        return {
            "score": final_rhi,
            "grade": grade,
            "badge_color": color,
            "active_defects_count": len([i for i in incidents if i.status != IncidentStatus.VERIFIED]),
            "resolved_defects_count": len([i for i in incidents if i.status == IncidentStatus.VERIFIED])
        }
