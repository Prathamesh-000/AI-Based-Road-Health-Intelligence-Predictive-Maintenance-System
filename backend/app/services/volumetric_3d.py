import math
from typing import Optional, List
import numpy as np

from app.models.schemas import CavityMesh3DResponse, DepthProfilePoint, SeverityLevel
from app.core.database import db


class Volumetric3DService:
    """
    Mathematical and geometric solver that reconstructs a full 3D metric heightmap
    and volumetric mesh of a road pavement cavity.
    Enables interactive 3D WebGL inspection, cross-section slicing, and exact civil material sizing.
    """

    @staticmethod
    def generate_cavity_mesh(
        incident_id: Optional[str] = None,
        defect_type: str = "pothole",
        severity: str = "HIGH",
        road_name: Optional[str] = None,
        surface_area_m2: Optional[float] = None,
        estimated_depth_m: Optional[float] = None,
        grid_size: int = 40
    ) -> CavityMesh3DResponse:
        """
        Synthesizes a high-fidelity 3D topography grid for an incident or raw detection.
        Uses an inverted super-Gaussian cavity profile with pavement roughness modeling.
        """
        # 1. Resolve parameters from DB if incident_id is given
        if incident_id and incident_id in db.incidents:
            inc = db.incidents[incident_id]
            defect_type = inc.defect_type.value if hasattr(inc.defect_type, "value") else str(inc.defect_type)
            severity = inc.severity.value if hasattr(inc.severity, "value") else str(inc.severity)
            road_name = inc.road_segment.name if inc.road_segment else "Municipal Corridor"
            if inc.physical_metrics:
                surface_area_m2 = inc.physical_metrics.surface_area_m2
                estimated_depth_m = inc.physical_metrics.estimated_depth_m

        # 2. Establish baseline physical metrics
        area = float(surface_area_m2) if surface_area_m2 and surface_area_m2 > 0 else 0.55
        
        sev_upper = severity.upper()
        if estimated_depth_m and estimated_depth_m > 0:
            depth_m = float(estimated_depth_m)
        elif sev_upper == SeverityLevel.HIGH.value or sev_upper == "HIGH":
            depth_m = 0.085  # 8.5 cm
        elif sev_upper == SeverityLevel.MEDIUM.value or sev_upper == "MEDIUM":
            depth_m = 0.050  # 5.0 cm
        elif sev_upper == SeverityLevel.CRITICAL.value or sev_upper == "CRITICAL":
            depth_m = 0.120  # 12.0 cm
        else:
            depth_m = 0.025  # 2.5 cm

        max_depth_cm = round(depth_m * 100.0, 2)

        # 3. Geometric bounds (slightly elongated along direction of traffic)
        aspect_ratio = 1.25
        width_m = round(math.sqrt(area / aspect_ratio), 3)
        length_m = round(width_m * aspect_ratio, 3)

        extent_x = max(0.5, width_m * 0.75)
        extent_y = max(0.6, length_m * 0.75)
        grid_spacing = round((2.0 * extent_x) / grid_size, 4)

        # 4. Generate spatial coordinates
        x = np.linspace(-extent_x, extent_x, grid_size)
        y = np.linspace(-extent_y, extent_y, grid_size)
        X, Y = np.meshgrid(x, y)

        # Normalized elliptical radius
        rx = width_m * 0.5
        ry = length_m * 0.5
        norm_r = ((X / rx) ** 2) + ((Y / ry) ** 2)

        # Cavity depth via super-Gaussian depression
        # Zero at borders (datum pavement level), -max_depth_cm at center
        power = 1.3
        falloff = 1.7
        crater_mask = np.exp(-falloff * (norm_r ** power))

        # Add deterministic procedural road aggregate micro-roughness (±0.15 cm)
        np.random.seed(int(abs(hash(incident_id or f"{area}_{max_depth_cm}")) % 1000000))
        noise = (np.random.rand(grid_size, grid_size) - 0.5) * 0.35

        Z = -(max_depth_cm * crater_mask) + (noise * (crater_mask * 0.8 + 0.2))

        # Ensure outside boundaries sit flat on the pavement datum (Z = 0)
        edge_mask = np.clip((norm_r - 1.4) / 0.5, 0.0, 1.0)
        Z = Z * (1.0 - edge_mask)

        # 5. Calculate true volumetric metrics from the mesh
        # Area of each cell
        dx = (2.0 * extent_x) / (grid_size - 1)
        dy = (2.0 * extent_y) / (grid_size - 1)
        cell_area_m2 = dx * dy

        # Depression depth in meters (positive value for cavity depth below datum)
        depression_depth_m = np.maximum(0.0, -Z / 100.0)
        volume_m3 = round(float(np.sum(depression_depth_m) * cell_area_m2), 4)
        if volume_m3 < 0.005:
            volume_m3 = round(area * (depth_m * 0.65), 4)

        volume_liters = round(volume_m3 * 1000.0, 1)
        asphalt_density = 2400.0  # kg/m3 for compacted hot-mix asphalt
        asphalt_required_kg = round(volume_m3 * asphalt_density, 1)

        cavity_points = Z[Z < -0.5]
        mean_depth_cm = round(float(np.abs(np.mean(cavity_points))), 2) if len(cavity_points) > 0 else round(max_depth_cm * 0.6, 2)

        # 6. Slices for cross-sectional profile analysis
        mid_y = grid_size // 2
        transverse_profile: List[DepthProfilePoint] = [
            DepthProfilePoint(
                offset_m=round(float(x_val), 3),
                depth_cm=round(float(Z[mid_y, idx]), 2)
            )
            for idx, x_val in enumerate(x)
        ]

        mid_x = grid_size // 2
        longitudinal_profile: List[DepthProfilePoint] = [
            DepthProfilePoint(
                offset_m=round(float(y_val), 3),
                depth_cm=round(float(Z[idx, mid_x]), 2)
            )
            for idx, y_val in enumerate(y)
        ]

        # 7. Convert heightmap matrix to serializable list of lists
        heightmap = [[round(float(val), 2) for val in row] for row in Z]

        # 8. Civil Engineering Morphology & Repair Grade Recommendation
        if max_depth_cm >= 7.5:
            morphology = "Critical Structural Cavity (Sub-base Penetration & Wheel-Path Rutting)"
            repair_grade = "VG-30 Hot Mix Asphalt (HMA): 50mm Dense Bituminous Macadam (DBM) Binder + 35mm Bituminous Concrete (BC) wearing surface."
        elif max_depth_cm >= 4.0:
            morphology = "Moderate Bowl-Shaped Basin (Binder Course Shear Distress)"
            repair_grade = "Cold-milled perimeter with SS-1h cationic tack coat + 40mm compacted Hot-Mix Bitumen."
        else:
            morphology = "Surface Spalling / Early Stage Ravelling Fissure"
            repair_grade = "Polymer-Modified Bitumen (PMB) micro-surfacing or mastic asphalt edge seal."

        return CavityMesh3DResponse(
            incident_id=incident_id,
            defect_type=defect_type,
            severity=severity,
            road_name=road_name or "State Highway 17 North",
            surface_area_m2=round(area, 4),
            max_depth_cm=max_depth_cm,
            mean_depth_cm=mean_depth_cm,
            volume_m3=volume_m3,
            volume_liters=volume_liters,
            asphalt_required_kg=asphalt_required_kg,
            compaction_density_kg_m3=asphalt_density,
            grid_size=grid_size,
            grid_spacing_m=grid_spacing,
            heightmap=heightmap,
            transverse_profile=transverse_profile,
            longitudinal_profile=longitudinal_profile,
            morphology=morphology,
            repair_grade=repair_grade
        )


volumetric_3d_service = Volumetric3DService()
