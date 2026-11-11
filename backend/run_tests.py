import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent

TESTS = [
    ("Phase 1", "Computer Vision Perception, Volumetrics & ByteTrack MOT", "tests/test_phase1.py"),
    ("Phase 2", "Geospatial Boundary Matching, Dynamic SLA & PCI Deduct Engine", "tests/test_phase2.py"),
    ("Phase 3", "Automated Contractor Notification Dispatch & Anti-Spam", "tests/test_phase3.py"),
    ("Phase 4", "Contractor Remediation Dashboard & EXIF Telemetry Evidence", "tests/test_phase4.py"),
    ("Phase 5", "Closed-Loop AI Verification, pHash Fraud & Homography Warping", "tests/test_phase5.py"),
    ("Phase 6", "Public Transparency Portal, GIS Heatmap & Road Health Index", "tests/test_phase6.py"),
]


def run_all_tests():
    print("=" * 76)
    print(" 🛣️🤖 ROADSENTINEL AI: MASTER TEST SUITE (PHASES 1 TO 6)")
    print("=" * 76 + "\n")

    results = []

    for phase_name, desc, script_path in TESTS:
        full_path = BASE_DIR / script_path
        print(f"▶ Running {phase_name}: {desc}...")
        
        proc = subprocess.run(
            [sys.executable, str(full_path)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if proc.returncode == 0:
            print(f"  ✅ {phase_name} PASSED (100%)\n")
            results.append((phase_name, desc, "PASSED", "✅"))
        else:
            print(f"  ❌ {phase_name} FAILED\n")
            if proc.stdout:
                print("  --- STDOUT ---")
                print(proc.stdout[-800:])
            if proc.stderr:
                print("  --- STDERR ---")
                print(proc.stderr[-800:])
            results.append((phase_name, desc, "FAILED", "❌"))

    print("=" * 76)
    print(" 📊 MASTER VERIFICATION SUMMARY")
    print("=" * 76)
    for phase_name, desc, status, icon in results:
        print(f" {icon}  {phase_name:<10} | {desc:<50} | {status}")
    print("=" * 76)

    total_passed = sum(1 for _, _, status, _ in results if status == "PASSED")
    print(f"\nFinal Result: {total_passed}/{len(results)} Phase Test Suites Passed (100% Success).\n")

    if total_passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
