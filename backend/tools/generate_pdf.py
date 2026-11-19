import os
import sys
import time
import json
import subprocess
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
HTML_PATH = ROOT_DIR / "docs" / "project_poster.html"
PDF_PATH = ROOT_DIR / "docs" / "RoadSentinel_AI_Project_Poster.pdf"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

browser_bin = CHROME_PATH if CHROME_PATH.exists() else EDGE_PATH
print(f"[generate_pdf] Using browser binary: {browser_bin}")

# Launch browser with headless print-to-pdf
file_url = HTML_PATH.as_uri()
print(f"[generate_pdf] Converting {file_url} -> {PDF_PATH}")

cmd = [
    str(browser_bin),
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
    "--allow-file-access-from-files",
    "--enable-local-file-accesses",
    "--run-all-compositor-stages-before-draw",
    "--no-pdf-header-footer",
    f"--print-to-pdf={PDF_PATH}",
    file_url
]

proc = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", proc.returncode)
print("Stdout:", proc.stdout)
print("Stderr:", proc.stderr)

if PDF_PATH.exists():
    size = PDF_PATH.stat().st_size
    print(f"[generate_pdf] Output PDF size: {size} bytes")
else:
    print("[generate_pdf] PDF was not generated.")
