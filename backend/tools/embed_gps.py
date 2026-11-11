"""
RoadSentinel AI - Video GPS Geotagging Utility
Injects standard ISO 6709 QuickTime/MP4 location metadata atom into any video file.
Enables automatic spatial telemetry detection for dashcam & drone footage.
"""

import sys
import struct
import argparse
from pathlib import Path


def embed_iso6709_gps(video_path: str, latitude: float, longitude: float, output_path: str = None) -> str:
    src = Path(video_path)
    if not src.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    if output_path is None:
        output_path = str(src.parent / f"{src.stem}_geotagged{src.suffix}")
    dst = Path(output_path)

    # Format latitude and longitude into ISO 6709 format: e.g. +18.520400+073.856700/
    lat_sign = "+" if latitude >= 0 else "-"
    lon_sign = "+" if longitude >= 0 else "-"
    lat_str = f"{lat_sign}{abs(latitude):09.6f}"
    lon_str = f"{lon_sign}{abs(longitude):010.6f}"
    iso_str = f"{lat_str}{lon_str}/".encode("ascii")

    # Construct standard QuickTime / MP4 User Data atom (udta) with ISO 6709 coordinates
    atom_type = b"udta"
    atom_len = struct.pack(">I", 8 + len(iso_str))
    geotag_atom = atom_len + atom_type + iso_str

    with open(src, "rb") as f_in:
        video_bytes = f_in.read()

    with open(dst, "wb") as f_out:
        f_out.write(video_bytes)
        f_out.write(geotag_atom)

    print(f"[SUCCESS] Injected ISO 6709 coordinates ({latitude}, {longitude}) into: {dst}")
    return str(dst)


def main():
    parser = argparse.ArgumentParser(description="Embed GPS coordinates into an MP4/MOV video.")
    parser.add_argument("video", help="Path to video file (e.g. video.mp4)")
    parser.add_argument("latitude", type=float, help="Latitude (e.g. 18.520400)")
    parser.add_argument("longitude", type=float, help="Longitude (e.g. 73.856700)")
    parser.add_argument("-o", "--output", help="Optional output path")

    args = parser.parse_args()
    embed_iso6709_gps(args.video, args.latitude, args.longitude, args.output)


if __name__ == "__main__":
    main()
