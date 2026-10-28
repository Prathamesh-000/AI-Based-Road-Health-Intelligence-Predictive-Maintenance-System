from app.models.schemas import SeverityLevel, PhysicalMetrics
from app.core.config import (
    ASPHALT_DENSITY_KG_M3,
    DEFAULT_GSD_METERS_PER_PX,
    DEFAULT_DEPTH_HIGH_M,
    DEFAULT_DEPTH_MED_M,
    DEFAULT_DEPTH_LOW_M
)


class DistressQuantifier:
    """
    Physical volumetric solver converting 2D bounding boxes into real-world
    pothole volume (m³) and hot-mix asphalt repair tonnage (kg).
    """
    @staticmethod
    def calculate_metrics(
        box_width_px: float,
        box_height_px: float,
        severity: SeverityLevel,
        gsd: float = DEFAULT_GSD_METERS_PER_PX
    ) -> PhysicalMetrics:
        # 1. Surface Area on ground (m²)
        ground_width_m = box_width_px * gsd
        ground_height_m = box_height_px * gsd
        surface_area_m2 = round(ground_width_m * ground_height_m, 4)

        # 2. Defect Depth Approximation (m) based on civil distress severity
        if severity == SeverityLevel.HIGH:
            depth_m = DEFAULT_DEPTH_HIGH_M
        elif severity == SeverityLevel.MEDIUM:
            depth_m = DEFAULT_DEPTH_MED_M
        else:
            depth_m = DEFAULT_DEPTH_LOW_M

        # 3. Volumetric Displacement (m³)
        volume_m3 = round(surface_area_m2 * depth_m, 5)

        # 4. Compacted Hot-Mix Asphalt Weight (kg = V * 2400 kg/m³)
        asphalt_kg = round(volume_m3 * ASPHALT_DENSITY_KG_M3, 2)

        return PhysicalMetrics(
            surface_area_m2=surface_area_m2,
            estimated_depth_m=depth_m,
            volume_m3=volume_m3,
            asphalt_required_kg=asphalt_kg
        )

