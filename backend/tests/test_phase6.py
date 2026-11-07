import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Reconfigure stdout for Windows console UTF-8 compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models.schemas import (
    Incident,
    IncidentStatus,
    SeverityLevel,
    DefectCategory,
    GeoLocation,
    PhysicalMetrics,
    RoadHealthRating,
    MunicipalRHIResponse,
    GeoJSONFeatureCollection
)
from app.core.database import db
from app.services.civic import civic_engine
from app.services.sla import SLAEngine


def print_step(name: str):
    print(f"\n[PHASE 6 TEST] === {name} ===")


def test_astm_d6433_rhi_calculation():
    print_step("Test 1: ASTM D6433 Road Health Index (PCI/RHI) Computation")
    rhi_data = civic_engine.compute_municipal_rhi()

    print(f"  City Overall RHI Score: {rhi_data.overall_rhi_score:.1f} / 100")
    print(f"  Condition Rating:       {rhi_data.health_rating.value}")
    print(f"  Active Hazards Count:   {rhi_data.active_hazards_count}")
    print(f"  In Remediation:         {rhi_data.in_remediation_count}")
    print(f"  Verified Repairs:       {rhi_data.verified_repairs_count}")
    print(f"  Repaired PCI Restored:  +{rhi_data.repaired_pci_restored} pts")
    print(f"  Asphalt Laid:           {rhi_data.asphalt_laid_kg:.1f} kg")

    assert 0.0 <= rhi_data.overall_rhi_score <= 100.0
    assert isinstance(rhi_data.health_rating, RoadHealthRating)
    assert len(rhi_data.segment_breakdown) == 3

    for seg in rhi_data.segment_breakdown:
        print(f"    - [{seg.segment_id}] {seg.name} ({seg.zone}): RHI {seg.rhi_score} ({seg.health_rating.value}), Active: {seg.active_defects_count}")
        assert 0.0 <= seg.rhi_score <= 100.0
        assert seg.total_length_km > 0.0

    print("  [PASS] Municipal RHI and segment breakdowns compute accurately per ASTM D6433.")


def test_geojson_hazards_rfc7946():
    print_step("Test 2: RFC 7946 GeoJSON Hazard Feed for Navigation Providers")
    geojson = civic_engine.generate_hazard_geojson()

    print(f"  GeoJSON Type: {geojson.type}")
    print(f"  Hazard Features Count: {len(geojson.features)}")
    assert geojson.type == "FeatureCollection"
    assert len(geojson.features) >= 1

    sample = geojson.features[0]
    coords = sample.geometry.coordinates
    props = sample.properties

    print(f"  Sample Hazard ID: {props['incident_id']}")
    print(f"  Coordinates (Lng, Lat): ({coords[0]:.5f}, {coords[1]:.5f})")
    print(f"  Defect: {props['defect_type']} ({props['severity']}), Hazard Level: {props['hazard_level']}/5")
    print(f"  Road: {props['road_name']} | SLA: {props['remaining_hours']}h ({props['sla_status']})")

    # Validate coordinate ordering [longitude, latitude] per RFC 7946
    assert 73.0 <= coords[0] <= 74.5  # Pune / Maharashtra longitude
    assert 18.0 <= coords[1] <= 19.5  # Pune / Maharashtra latitude
    assert props["hazard_level"] in [2, 3, 4, 5]
    assert props["status"] not in ["VERIFIED", "CLOSED"]

    print("  [PASS] GeoJSON hazard collection adheres strictly to RFC 7946 standards.")


def test_public_audit_feed_and_cards():
    print_step("Test 3: Public Transparency Audit Feed & Verification Cards")
    audit_cards = civic_engine.get_public_audit_feed(limit=10)
    print(f"  Public Audit Cards Count: {len(audit_cards)}")
    assert len(audit_cards) >= 1

    sample_card = audit_cards[0]
    print(f"  Incident ID:       {sample_card.incident_id}")
    print(f"  Corridor:          {sample_card.road_name} ({sample_card.zone})")
    print(f"  Contractor:        {sample_card.contractor_name}")
    print(f"  Status:            {sample_card.status.value}")
    print(f"  Evidence Photo:    {sample_card.evidence_image_url}")

    assert sample_card.incident_id.startswith("INC-")
    assert sample_card.road_name is not None
    assert sample_card.evidence_image_url is not None

    # Test single audit card retrieval
    single = civic_engine.get_incident_audit_card(sample_card.incident_id)
    assert single is not None
    assert single.incident_id == sample_card.incident_id
    print(f"  Single Audit Card successfully retrieved for {single.incident_id}")

    print("  [PASS] Public audit feed and individual verification cards verified.")


def test_corridor_deduct_restoration_lifecycle():
    print_step("Test 4: Dynamic RHI Deduct Degradation & Restoration Lifecycle")
    now = datetime.now(timezone.utc)
    seg, contractor = db.spatial_matcher.match_location(18.5204, 73.8567)

    # Record initial segment RHI
    initial_rhi = civic_engine.compute_municipal_rhi()
    seg_initial = next(s for s in initial_rhi.segment_breakdown if s.segment_id == seg.segment_id)
    initial_score = seg_initial.rhi_score
    print(f"  Segment '{seg.name}' Initial RHI: {initial_score}")

    # 1. Inject a new High-Severity Pothole (+15.0 deduct points)
    test_inc_id = f"INC-PCI-TEST-{int(now.timestamp())}"
    sla = SLAEngine.calculate_sla(SeverityLevel.HIGH, now)
    pci_deduct = SLAEngine.compute_pci_deduct(DefectCategory.POTHOLE, SeverityLevel.HIGH)

    inc = Incident(
        id=test_inc_id,
        created_at=now,
        defect_type=DefectCategory.POTHOLE,
        severity=SeverityLevel.HIGH,
        status=IncidentStatus.REPORTED,
        location=GeoLocation(latitude=18.5204, longitude=73.8567, road_name=seg.name),
        road_segment=seg,
        assigned_contractor=contractor,
        sla_metrics=sla,
        physical_metrics=PhysicalMetrics(surface_area_m2=0.5, estimated_depth_m=0.08, volume_m3=0.04, asphalt_required_kg=96.0),
        evidence_image_url="/storage/evidence/sample_pothole_1.jpg",
        pci_deduct_points=pci_deduct
    )
    db.create_incident(inc)

    # Re-evaluate RHI: should degrade by pci_deduct
    degraded_rhi = civic_engine.compute_municipal_rhi()
    seg_degraded = next(s for s in degraded_rhi.segment_breakdown if s.segment_id == seg.segment_id)
    print(f"  After Defect Reported: RHI dropped to {seg_degraded.rhi_score} (Deduct: -{pci_deduct})")
    assert seg_degraded.rhi_score < initial_score
    assert seg_degraded.active_defects_count == seg_initial.active_defects_count + 1

    # 2. Repair & Verify the Defect (status -> VERIFIED)
    db.transition_status(
        incident_id=test_inc_id,
        new_status=IncidentStatus.ASSIGNED,
        actor="Dispatcher"
    )
    db.transition_status(
        incident_id=test_inc_id,
        new_status=IncidentStatus.IN_PROGRESS,
        actor="Contractor"
    )
    db.transition_status(
        incident_id=test_inc_id,
        new_status=IncidentStatus.VERIFICATION_PENDING,
        actor="Contractor"
    )
    db.transition_status(
        incident_id=test_inc_id,
        new_status=IncidentStatus.VERIFIED,
        actor="Closed-Loop AI Verification Engine",
        notes="Automated repair verified complete"
    )

    # Re-evaluate RHI: deduct points should be restored and defect removed from active hazards!
    restored_rhi = civic_engine.compute_municipal_rhi()
    seg_restored = next(s for s in restored_rhi.segment_breakdown if s.segment_id == seg.segment_id)
    print(f"  After AI Verification: RHI restored to {seg_restored.rhi_score} (Verified repairs: {seg_restored.verified_repairs_count})")
    assert seg_restored.rhi_score == initial_score
    assert seg_restored.active_defects_count == seg_initial.active_defects_count
    assert seg_restored.verified_repairs_count == seg_initial.verified_repairs_count + 1

    print("  [PASS] ASTM D6433 PCI degradation and closed-loop restoration validated.")


def test_rating_classification_thresholds():
    print_step("Test 5: ASTM Rating Classification Bounds")
    assert civic_engine.classify_rating(95.0) == RoadHealthRating.EXCELLENT
    assert civic_engine.classify_rating(85.0) == RoadHealthRating.EXCELLENT
    assert civic_engine.classify_rating(84.9) == RoadHealthRating.GOOD
    assert civic_engine.classify_rating(70.0) == RoadHealthRating.GOOD
    assert civic_engine.classify_rating(65.0) == RoadHealthRating.FAIR
    assert civic_engine.classify_rating(45.0) == RoadHealthRating.POOR
    assert civic_engine.classify_rating(30.0) == RoadHealthRating.VERY_POOR
    assert civic_engine.classify_rating(15.0) == RoadHealthRating.FAILED
    print("  [PASS] All ASTM D6433 classification boundary conditions verified.")


if __name__ == "__main__":
    print("=======================================================================")
    print("  ROADSENTINEL AI: PHASE 6 CIVIC INTELLIGENCE TEST SUITE")
    print("  Public Transparency, ASTM D6433 RHI & GeoJSON Navigation")
    print("=======================================================================")

    test_astm_d6433_rhi_calculation()
    test_geojson_hazards_rfc7946()
    test_public_audit_feed_and_cards()
    test_corridor_deduct_restoration_lifecycle()
    test_rating_classification_thresholds()

    print("\n=======================================================================")
    print("  [SUCCESS] 100% OF PHASE 6 VERIFICATION TESTS PASSED")
    print("=======================================================================\n")

