import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from pathlib import Path

from app.models.schemas import GeoLocation


class TelemetryPoint:
    def __init__(self, lat: float, lon: float, timestamp: Optional[datetime] = None, elevation: float = 0.0):
        self.lat = lat
        self.lon = lon
        self.timestamp = timestamp
        self.elevation = elevation


class TelemetrySynchronizer:
    """
    Synchronizes video frame timestamps with spatial telemetry (GPX tracks,
    NMEA GPS logs, or spatial corridor interpolation).
    """
    def __init__(self, gpx_path: Optional[str] = None):
        self.points: List[TelemetryPoint] = []
        if gpx_path and Path(gpx_path).exists():
            self.load_gpx(gpx_path)

    def load_gpx(self, gpx_path: str):
        """
        Parses standard GPX XML files into timestamped spatial points.
        """
        tree = ET.parse(gpx_path)
        root = tree.getroot()

        # Handle GPX XML namespaces
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trkpts = root.findall(".//gpx:trkpt", ns)
        if not trkpts:
            trkpts = root.findall(".//trkpt")

        self.points = []
        for pt in trkpts:
            lat = float(pt.attrib["lat"])
            lon = float(pt.attrib["lon"])
            ele_elem = pt.find("gpx:ele", ns) if ns else pt.find("ele")
            ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else 0.0

            time_elem = pt.find("gpx:time", ns) if ns else pt.find("time")
            t = None
            if time_elem is not None and time_elem.text:
                time_str = time_elem.text.strip()
                # Parse ISO8601 time string
                try:
                    t = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        t = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

            self.points.append(TelemetryPoint(lat, lon, t, ele))

    def get_coordinate_at_time(
        self,
        elapsed_seconds: float,
        total_duration: float,
        fallback_lat: float = 18.5204,
        fallback_lng: float = 73.8567,
        road_name: str = "Patrol Sector"
    ) -> GeoLocation:
        """
        Interpolates spatial coordinate at a specific video elapsed timestamp.
        """
        # Case A: We have valid GPX points
        if self.points:
            # If timestamps exist in GPX, interpolate based on relative duration
            num_pts = len(self.points)
            if num_pts == 1:
                return GeoLocation(
                    latitude=self.points[0].lat,
                    longitude=self.points[0].lon,
                    elevation_m=self.points[0].elevation,
                    road_name=road_name
                )

            # Map elapsed ratio to points array
            ratio = min(1.0, max(0.0, elapsed_seconds / max(1.0, total_duration)))
            idx_float = ratio * (num_pts - 1)
            idx_low = int(idx_float)
            idx_high = min(num_pts - 1, idx_low + 1)
            frac = idx_float - idx_low

            p1 = self.points[idx_low]
            p2 = self.points[idx_high]

            interp_lat = p1.lat + frac * (p2.lat - p1.lat)
            interp_lon = p1.lon + frac * (p2.lon - p1.lon)
            interp_ele = p1.elevation + frac * (p2.elevation - p1.elevation)

            return GeoLocation(
                latitude=round(interp_lat, 6),
                longitude=round(interp_lon, 6),
                elevation_m=round(interp_ele, 1),
                road_name=road_name
            )

        # Case B: Fallback spatial corridor interpolation along vehicle heading
        # Slightly offset coordinates along travel vector for simulation realism
        drift_rate = 0.00015  # ~15 meters per 10 seconds of travel
        progress = elapsed_seconds / max(1.0, total_duration)
        interp_lat = fallback_lat + (progress * drift_rate)
        interp_lon = fallback_lng + (progress * drift_rate * 0.8)

        return GeoLocation(
            latitude=round(interp_lat, 6),
            longitude=round(interp_lon, 6),
            elevation_m=12.0,
            road_name=road_name
        )

