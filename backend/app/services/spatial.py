import math
from typing import Tuple, Optional, List, Dict
from app.models.schemas import RoadSegment, Contractor


# Pre-registered Municipal Contractors
REGISTERED_CONTRACTORS: Dict[str, Contractor] = {
    "CTR-001": Contractor(
        id="CTR-001",
        name="Apex Paving Solutions",
        company="Apex Infrastructure Ltd.",
        email="dispatch@apexinfra.com",
        phone="+1-800-555-0199",
        assigned_zones=["Zone 1 - North Corridor", "Sector 4A Arterials"],
        performance_score=94.5,
        completed_repairs=142
    ),
    "CTR-002": Contractor(
        id="CTR-002",
        name="MetroRoad Maintenance Corp",
        company="MetroRoad Civil Works",
        email="repairs@metroroad.org",
        phone="+1-800-555-0245",
        assigned_zones=["Zone 2 - Downtown Central", "Highway 101 Access"],
        performance_score=91.0,
        completed_repairs=98
    ),
    "CTR-003": Contractor(
        id="CTR-003",
        name="Civic Asphalt Engineering",
        company="Civic Build Partners",
        email="contractor@civicasphalt.net",
        phone="+1-800-555-0378",
        assigned_zones=["Zone 3 - Eastern Industrial", "Bypass Ring Road"],
        performance_score=88.5,
        completed_repairs=67
    )
}

# Pre-registered Road Segments with Spatial Bounds [min_lat, min_lng, max_lat, max_lng]
REGISTERED_ROAD_SEGMENTS: List[RoadSegment] = [
    RoadSegment(
        segment_id="SEG-101",
        name="State Highway 17 North",
        zone="Zone 1 - North Corridor",
        contractor_id="CTR-001",
        bounds=[18.5150, 73.8450, 18.5450, 73.8750],
        total_length_km=4.8
    ),
    RoadSegment(
        segment_id="SEG-102",
        name="Central Boulevard & Ring Road",
        zone="Zone 2 - Downtown Central",
        contractor_id="CTR-002",
        bounds=[18.4900, 73.8200, 18.5200, 73.8500],
        total_length_km=6.2
    ),
    RoadSegment(
        segment_id="SEG-103",
        name="Eastern Industrial Bypass",
        zone="Zone 3 - Eastern Industrial",
        contractor_id="CTR-003",
        bounds=[18.5300, 73.8800, 18.5700, 73.9200],
        total_length_km=5.5
    )
]


class GeospatialMatcher:
    """
    Spatial boundary matcher using bounding-box spatial indexing
    and Haversine proximity calculations (PostGIS ST_Contains / ST_DWithin logic).
    """
    def __init__(self):
        self.segments = REGISTERED_ROAD_SEGMENTS
        self.contractors = REGISTERED_CONTRACTORS

    @staticmethod
    def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def match_location(self, lat: float, lng: float, road_hint: Optional[str] = None) -> Tuple[RoadSegment, Contractor]:
        """
        Matches coordinates to the appropriate municipal road segment and contractor.
        1. Checks exact bounding box intersection.
        2. If outside, finds the closest road segment by centroid distance.
        """
        # 1. Check exact polygon / bounding box containment
        for seg in self.segments:
            min_lat, min_lng, max_lat, max_lng = seg.bounds
            if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                contractor = self.contractors.get(seg.contractor_id, list(self.contractors.values())[0])
                return seg, contractor

        # 2. Match nearest segment by centroid distance
        best_seg = self.segments[0]
        min_dist = float("inf")

        for seg in self.segments:
            min_lat, min_lng, max_lat, max_lng = seg.bounds
            mid_lat = (min_lat + max_lat) / 2.0
            mid_lng = (min_lng + max_lng) / 2.0
            dist = self.haversine_distance_m(lat, lng, mid_lat, mid_lng)

            if dist < min_dist:
                min_dist = dist
                best_seg = seg

        contractor = self.contractors.get(best_seg.contractor_id, list(self.contractors.values())[0])
        return best_seg, contractor

    def get_contractor(self, contractor_id: str) -> Optional[Contractor]:
        return self.contractors.get(contractor_id)

    def list_all_segments(self) -> List[RoadSegment]:
        return self.segments

    def list_all_contractors(self) -> List[Contractor]:
        return list(self.contractors.values())

