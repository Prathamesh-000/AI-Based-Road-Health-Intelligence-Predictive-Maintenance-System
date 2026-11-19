import os
import struct
from pathlib import Path
from datetime import datetime, timezone, timedelta

def setup_demo():
    src_video = Path(r"C:\Users\PC Point\.gemini\antigravity\brain\4e808583-788f-4701-9e0f-ab7c9d793e2f\.user_uploaded\media_1795100629864_86d1a450.mp4")
    upload_dir = Path("backend/storage/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    dst_video = upload_dir / "sample_patrol_with_gps.mp4"

    # 1. Read uploaded video
    with open(src_video, "rb") as f_in:
        data = f_in.read()

    # 2. Append standard ISO-6709 QuickTime atom: +18.520400+073.856700/
    tag = b"+18.520400+073.856700/"
    atom_type = b"udta"
    atom_len = struct.pack(">I", 8 + len(tag))
    geotag_atom = atom_len + atom_type + tag

    with open(dst_video, "wb") as f_out:
        f_out.write(data + geotag_atom)

    print(f"[1/3] Created new demo video: {dst_video} ({dst_video.stat().st_size} bytes)")

    # 3. Generate 28-second synchronized GPX track along State Highway 17 North
    gpx_path = upload_dir / "test_route.gpx"
    start_time = datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)
    duration_sec = 28

    start_lat, start_lon = 18.520400, 73.856700
    end_lat, end_lon = 18.523550, 73.859800

    trkpts_xml = []
    for sec in range(duration_sec + 1):
        frac = sec / duration_sec
        lat = start_lat + frac * (end_lat - start_lat)
        lon = start_lon + frac * (end_lon - start_lon)
        ele = 560.0 + frac * 4.5
        t_str = (start_time + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
        trkpts_xml.append(
            f"      <trkpt lat=\"{lat:.6f}\" lon=\"{lon:.6f}\">\n"
            f"        <ele>{ele:.1f}</ele>\n"
            f"        <time>{t_str}</time>\n"
            f"      </trkpt>"
        )

    pts_joined = "\n".join(trkpts_xml)
    gpx_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<gpx version=\"1.1\" creator=\"RoadSentinel AI Telemetry Engine\" xmlns=\"http://www.topografix.com/GPX/1/1\">\n"
        "  <metadata>\n"
        "    <name>State Highway 17 North - High Precision Patrol Corridor</name>\n"
        f"    <time>{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>\n"
        "  </metadata>\n"
        "  <trk>\n"
        "    <name>State Highway 17 North Patrol Run</name>\n"
        "    <trkseg>\n"
        f"{pts_joined}\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>\n"
    )

    with open(gpx_path, "w", encoding="utf-8") as f:
        f.write(gpx_xml)

    print(f"[2/3] Generated synchronized GPX route ({duration_sec + 1} points): {gpx_path}")

    # 4. Remove old initial video and old temporary uploads
    removed_count = 0
    for p in upload_dir.glob("patrol_*.mp4"):
        try:
            p.unlink()
            removed_count += 1
            print(f"   - Removed old initial file: {p.name}")
        except Exception as e:
            print(f"   ! Could not remove {p.name}: {e}")

    for p in upload_dir.glob("telemetry_*.gpx"):
        try:
            p.unlink()
            removed_count += 1
            print(f"   - Removed old telemetry file: {p.name}")
        except Exception as e:
            print(f"   ! Could not remove {p.name}: {e}")

    print(f"[3/3] Cleaned up {removed_count} old initial video and telemetry files.")

if __name__ == "__main__":
    setup_demo()
