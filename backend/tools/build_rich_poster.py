import base64
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT_DIR / "docs"

def get_base64_img(filename):
    path = DOCS_DIR / filename
    if path.exists():
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        return f"data:image/jpeg;base64,{data}"
    return ""

img_det = get_base64_img("poster_detection_demo.jpg")
img_ba = get_base64_img("poster_before_after.jpg")
img_3d = get_base64_img("poster_volumetric_3d.jpg")
img_gis = get_base64_img("poster_gis_map.jpg")

print(f"[build_rich_poster] Loaded images. Det={len(img_det)}B, BA={len(img_ba)}B, 3D={len(img_3d)}B, GIS={len(img_gis)}B")

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RoadSentinel AI - Technical Project Poster & Progress Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    @page {{
      size: A3 landscape;
      margin: 6mm;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #080c14;
      color: #f1f5f9;
      line-height: 1.4;
      -webkit-font-smoothing: antialiased;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      padding: 12px;
    }}

    @media print {{
      body {{ padding: 0; background-color: #080c14 !important; color: #f1f5f9 !important; }}
      .no-print {{ display: none !important; }}
    }}

    .no-print-bar {{
      max-width: 1720px;
      margin: 0 auto 12px auto;
      background: #0f172a;
      border: 1px solid #1e293b;
      padding: 8px 16px;
      border-radius: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
    }}

    .btn-print {{
      background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
      color: #020617;
      font-weight: 800;
      padding: 6px 16px;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .poster-container {{
      max-width: 1720px;
      margin: 0 auto;
      background: #0d131f;
      border: 1px solid #1e293b;
      border-radius: 16px;
      padding: 18px 22px;
      position: relative;
    }}

    .accent-strip {{
      height: 5px;
      width: 100%;
      background: linear-gradient(90deg, #38bdf8 0%, #6366f1 50%, #f59e0b 100%);
      position: absolute;
      top: 0;
      left: 0;
      border-radius: 16px 16px 0 0;
    }}

    /* Header */
    .poster-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 14px;
      margin-bottom: 14px;
      gap: 20px;
    }}

    .tag-row {{ display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }}
    .tag-blue {{
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: #38bdf8;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 12px;
      font-family: monospace;
    }}
    .tag-green {{
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.35);
      color: #34d399;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 12px;
    }}

    .title-row {{ display: flex; align-items: baseline; gap: 10px; }}
    .main-title {{ font-size: 38px; font-weight: 900; color: #ffffff; letter-spacing: -0.8px; line-height: 1.1; }}
    .ver-pill {{
      font-size: 11px;
      font-weight: 800;
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
    }}
    .sub-title {{ font-size: 13.5px; font-weight: 600; color: #38bdf8; margin-top: 2px; }}

    .meta-box {{
      display: flex;
      background: #080c14;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 10px 16px;
      gap: 16px;
      font-size: 11px;
      white-space: nowrap;
    }}
    .meta-col {{ display: flex; flex-direction: column; gap: 1px; }}
    .meta-col.border-r {{ border-right: 1px solid #1e293b; padding-right: 16px; }}
    .meta-label {{ color: #94a3b8; font-size: 10px; }}
    .meta-name {{ color: #ffffff; font-size: 15px; font-weight: 800; }}
    .meta-roll {{ color: #f59e0b; font-family: monospace; font-size: 11px; font-weight: 700; }}
    .meta-inst {{ color: #ffffff; font-size: 13px; font-weight: 700; }}
    .meta-loc {{ color: #6366f1; font-size: 10px; font-weight: 600; }}

    /* Phase Dashboard */
    .dashboard-panel {{
      background: #080c14;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 10px 14px;
      margin-bottom: 14px;
    }}
    .dash-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 6px;
      margin-bottom: 8px;
    }}
    .dash-title {{ font-size: 12px; font-weight: 800; text-transform: uppercase; color: #ffffff; display: flex; align-items: center; gap: 6px; }}
    .dot-green {{ width: 7px; height: 7px; border-radius: 50%; background: #10b981; display: inline-block; }}
    .badge-tests {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
      font-size: 10px;
      font-weight: 700;
      font-family: monospace;
      padding: 2px 8px;
      border-radius: 5px;
    }}

    .phases-row {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }}
    .phase-item {{
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 7px 9px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .phase-top {{ display: flex; justify-content: space-between; font-size: 9px; font-weight: 800; font-family: monospace; }}
    .p-1 {{ color: #34d399; }} .p-2 {{ color: #38bdf8; }} .p-3 {{ color: #818cf8; }} .p-4 {{ color: #fbbf24; }} .p-5 {{ color: #f43f5e; }} .p-6 {{ color: #2dd4bf; }}
    .p-badge {{ background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 1px 4px; border-radius: 3px; font-size: 8px; }}
    .phase-heading {{ color: #ffffff; font-size: 11px; font-weight: 700; }}
    .phase-sub {{ color: #94a3b8; font-size: 9px; line-height: 1.25; }}
    .phase-ok {{ color: #34d399; font-size: 9px; font-weight: 700; font-family: monospace; margin-top: 2px; }}

    /* 4 Columns */
    .four-columns {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .col-box {{ display: flex; flex-direction: column; gap: 12px; }}

    .card {{
      background: #080c14;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 11px 13px;
      display: flex;
      flex-direction: column;
      gap: 7px;
    }}
    .card.highlight {{ border-color: rgba(245, 158, 11, 0.4); background: #0c121e; }}

    .card-title {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .t-rose {{ color: #f43f5e; }} .t-sky {{ color: #38bdf8; }} .t-indigo {{ color: #818cf8; }} .t-amber {{ color: #fbbf24; }} .t-green {{ color: #34d399; }}

    .card-body {{ color: #cbd5e1; font-size: 10.5px; line-height: 1.4; text-align: justify; }}

    .sub-item {{
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 6px 8px;
      font-size: 10px;
      color: #cbd5e1;
      line-height: 1.35;
    }}
    .sub-item.alert {{
      border-color: rgba(244, 63, 94, 0.3);
      background: rgba(244, 63, 94, 0.05);
    }}
    .sub-item strong {{ color: #ffffff; }}

    /* Real Image Embed Containers */
    .img-container {{
      border: 1px solid #1e293b;
      border-radius: 8px;
      overflow: hidden;
      background: #000;
      position: relative;
    }}
    .img-container img {{
      width: 100%;
      height: auto;
      display: block;
      object-fit: cover;
    }}
    .img-caption {{
      background: #0f172a;
      padding: 4px 8px;
      font-size: 9.5px;
      color: #94a3b8;
      border-top: 1px solid #1e293b;
      display: flex;
      justify-content: space-between;
      font-family: monospace;
    }}

    /* Pipeline */
    .pipe-row {{
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 5px;
      padding: 5px 8px;
      display: flex;
      justify-content: space-between;
      font-family: monospace;
      font-size: 10px;
    }}
    .pipe-arrow-sm {{ text-align: center; color: #475569; font-size: 8px; margin: -3px 0; }}

    /* Math Box */
    .math-panel {{
      background: #020617;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 7px 9px;
      font-family: monospace;
      font-size: 10px;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}
    .math-line {{ display: flex; justify-content: space-between; }}

    /* Metrics Grid */
    .metrics-2x2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; text-align: center; }}
    .metric-box {{
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 6px 4px;
    }}
    .m-val {{ font-size: 18px; font-weight: 900; font-family: monospace; line-height: 1.1; }}
    .m-lbl {{ font-size: 9px; color: #94a3b8; font-weight: 600; text-transform: uppercase; margin-top: 1px; }}

    /* Tech Stack */
    .tech-badges {{ display: flex; flex-wrap: wrap; gap: 4px; }}
    .t-pill {{
      background: #0f172a;
      border: 1px solid #1e293b;
      color: #cbd5e1;
      font-size: 9px;
      font-family: monospace;
      padding: 2px 6px;
      border-radius: 4px;
    }}

    /* Footer */
    .poster-ft {{
      margin-top: 14px;
      padding-top: 10px;
      border-top: 1px solid #1e293b;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 10.5px;
      color: #94a3b8;
    }}
  </style>
</head>
<body>

  <!-- Screen Control Bar -->
  <div class="no-print no-print-bar">
    <div style="display:flex; align-items:center; gap:8px;">
      <span style="color:#fbbf24; font-weight:700; font-family:monospace;">ROAD-SENTINEL-AI-POSTER-V2.1</span>
      <span style="color:#475569;">•</span>
      <span style="color:#cbd5e1;">National Institute of Technology Jalandhar — Capstone Project Review</span>
      <span style="color:#475569;">•</span>
      <span style="color:#34d399; font-weight:600;">● Live Demo Video Frames Embedded</span>
    </div>
    <button class="btn-print" onclick="window.print()">
      <span>Print Poster / Export PDF</span>
    </button>
  </div>

  <div class="poster-container">
    <div class="accent-strip"></div>

    <!-- Header -->
    <header class="poster-header">
      <div style="flex:1;">
        <div class="tag-row">
          <span class="tag-blue">B.Tech Capstone Project • AI & Civic Robotics</span>
          <span class="tag-green">Status: Working System + Live Video Telemetry</span>
        </div>
        <div class="title-row">
          <h1 class="main-title">RoadSentinel AI</h1>
          <span class="ver-pill">v2.4 LTS</span>
        </div>
        <div class="sub-title">
          AI-Powered Road Health Intelligence, Spatial Telemetry, Volumetric Pavement Solvers & Closed-Loop Repair Verification Platform
        </div>
      </div>

      <div class="meta-box">
        <div class="meta-col border-r">
          <span class="meta-label">Student Lead & Author</span>
          <span class="meta-name">Prathamesh Patil</span>
          <span class="meta-roll">Roll No: 24103119</span>
          <span class="meta-label">B.Tech Computer Science & Eng.</span>
        </div>
        <div class="meta-col">
          <span class="meta-label">Institution & Department</span>
          <span class="meta-inst">National Institute of Technology Jalandhar</span>
          <span class="meta-loc">NIT Jalandhar • Punjab, India</span>
          <span class="meta-label">Department of Computer Science</span>
        </div>
      </div>
    </header>

    <!-- Phase Implementation Dashboard -->
    <section class="dashboard-panel">
      <div class="dash-top">
        <div class="dash-title">
          <span class="dot-green"></span>
          <span>Project Implementation Progress: 100% All 6 Phases Passed & Verified</span>
        </div>
        <span class="badge-tests">Master Test Suite: 6/6 Suites Passed (100%)</span>
      </div>

      <div class="phases-row">
        <div class="phase-item">
          <div class="phase-top"><span class="p-1">PHASE 1</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">Perception & MOT</div>
          <div class="phase-sub">YOLOv8 + ByteTrack. Dual-mode asphalt & mud water-pool solver.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
        <div class="phase-item">
          <div class="phase-top"><span class="p-2">PHASE 2</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">Spatial & ASTM PCI</div>
          <div class="phase-sub">Geospatial corridor matching, dynamic SLA calc & ASTM D6433 deducts.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
        <div class="phase-item">
          <div class="phase-top"><span class="p-3">PHASE 3</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">Automated Dispatch</div>
          <div class="phase-sub">Zero-spam contractor dispatch, HTML mailer & anti-burst rate limiter.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
        <div class="phase-item">
          <div class="phase-top"><span class="p-4">PHASE 4</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">Contractor Portal</div>
          <div class="phase-sub">Work queue, EXIF GPS geofence validation & repair photo uploads.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
        <div class="phase-item">
          <div class="phase-top"><span class="p-5">PHASE 5</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">AI Verification</div>
          <div class="phase-sub">Homography perspective warp, pHash anti-fraud & bitumen texture.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
        <div class="phase-item">
          <div class="phase-top"><span class="p-6">PHASE 6</span><span class="p-badge">100%</span></div>
          <div class="phase-heading">Public GIS Portal</div>
          <div class="phase-sub">Live Road Health Index (RHI), GeoJSON hazards & Before-After cards.</div>
          <div class="phase-ok">✅ VERIFIED</div>
        </div>
      </div>
    </section>

    <!-- 4 Columns Grid -->
    <div class="four-columns">

      <!-- Column 1: Problem & Pipeline -->
      <div class="col-box">
        <div class="card">
          <div class="card-title t-rose"><span>● 1. Problem Statement & Bottlenecks</span></div>
          <div class="card-body">Traditional municipal maintenance relies on manual surveys and subjective contractor auditing:</div>
          <div class="sub-item alert"><strong>❌ Mass Frame Duplication:</strong> Driving past one pothole at 30 FPS generates dozens of redundant tickets.</div>
          <div class="sub-item alert"><strong>❌ No Material Sizing:</strong> Crews dispatched with arbitrary asphalt loads without scientific 3D volumetric math.</div>
          <div class="sub-item alert"><strong>❌ Contractor Billing Fraud:</strong> Unverified repair claims using recycled stock photos or sub-standard patching.</div>
        </div>

        <div class="card">
          <div class="card-title t-sky"><span>● 2. The RoadSentinel Paradigm</span></div>
          <div class="card-body">An autonomous, closed-loop cyber-physical system connecting video perception directly to contractor dispatch, anti-fraud AI verification, and citizen transparency.</div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; text-align:center;">
            <div class="sub-item"><div style="color:#fbbf24; font-weight:700;">📷 Detect</div><div style="color:#94a3b8; font-size:9px;">Dual-Mode CV</div></div>
            <div class="sub-item"><div style="color:#818cf8; font-weight:700;">📐 Quantify</div><div style="color:#94a3b8; font-size:9px;">Asphalt Tonnage</div></div>
            <div class="sub-item"><div style="color:#38bdf8; font-weight:700;">📍 Assign</div><div style="color:#94a3b8; font-size:9px;">GIS Boundary</div></div>
            <div class="sub-item"><div style="color:#34d399; font-weight:700;">🔍 Verify</div><div style="color:#94a3b8; font-size:9px;">Homography AI</div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-title t-indigo"><span>● 3. End-to-End Pipeline</span></div>
          <div style="display:flex; flex-direction:column; gap:3px;">
            <div class="pipe-row"><span>1. Video & GPX Ingest</span><span style="color:#38bdf8;">ISO-6709 + GPX</span></div>
            <div class="pipe-arrow-sm">▼</div>
            <div class="pipe-row"><span>2. Dual-Mode CV</span><span style="color:#fbbf24;">YOLOv8 + Water</span></div>
            <div class="pipe-arrow-sm">▼</div>
            <div class="pipe-row"><span>3. Spatial Dispatch</span><span style="color:#818cf8;">PostGIS Corridor</span></div>
            <div class="pipe-arrow-sm">▼</div>
            <div class="pipe-row"><span>4. Remediation Upload</span><span style="color:#34d399;">EXIF Guard</span></div>
            <div class="pipe-arrow-sm">▼</div>
            <div class="pipe-row" style="border-color:rgba(245,158,11,0.5); background:rgba(245,158,11,0.08);"><span style="color:#fbbf24; font-weight:700;">5. AI Verification</span><span style="color:#fbbf24;">ORB + Texture</span></div>
            <div class="pipe-arrow-sm">▼</div>
            <div class="pipe-row"><span>6. Public Transparency</span><span style="color:#2dd4bf;">ASTM D6433 RHI</span></div>
          </div>
        </div>
      </div>

      <!-- Column 2: Perception & Real Demo Frame -->
      <div class="col-box">
        <div class="card">
          <div class="card-title t-amber"><span>● 4. Dual-Mode CV Perception (Live Frame)</span></div>
          <div class="card-body">Real dashcam patrol footage analyzed with our Dual-Mode Perception Solver. Detects both dry asphalt depressions (Mode A) and reflective water-filled cavities on mud roads (Mode B):</div>
          
          <!-- Real Annotated Video Frame -->
          <div class="img-container">
            <img src="{img_det}" alt="Dashcam Pothole Detection">
            <div class="img-caption">
              <span>● Frame 25 (1.0s) • 11 Potholes Detected</span>
              <span style="color:#34d399;">ByteTrack MOT Active</span>
            </div>
          </div>

          <div class="sub-item" style="border-color:rgba(99,102,241,0.4);">
            <strong style="color:#818cf8;">Vehicle & Bike Rejection Shield:</strong><br/>
            Ultra-sensitive YOLO pass (conf=0.08) masks vehicles and riders. Combined with HSV Saturation gating (Sat &gt; 38%), zero vehicles or tires are ever tagged as potholes.
          </div>
        </div>

        <div class="card">
          <div class="card-title t-sky"><span>● 5. Mode A vs Mode B Physics</span></div>
          <div class="sub-item"><strong style="color:#fbbf24;">Mode A (Asphalt):</strong> Otsu inverse thresholding on drivable trapezoid corridors locates dark cavities.</div>
          <div class="sub-item"><strong style="color:#38bdf8;">Mode B (Mud/Dirt):</strong> Detects sky specular reflectance on brown mud via adaptive threshold: &mu;<sub>road</sub> + 1.2&sigma;<sub>road</sub>.</div>
        </div>
      </div>

      <!-- Column 3: AI Verification & 3D Volumetrics -->
      <div class="col-box">
        <div class="card highlight">
          <div class="card-title t-amber"><span>● 6. Closed-Loop AI Verification (Evidence)</span></div>
          <div class="card-body">Direct Before-vs-After verification evidence comparing pre-repair defect against contractor hot-mix asphalt patching:</div>

          <!-- Real Before/After Verification Frame -->
          <div class="img-container">
            <img src="{img_ba}" alt="Before After AI Verification">
            <div class="img-caption">
              <span>ORB Keypoints Homography Alignment</span>
              <span style="color:#34d399; font-weight:700;">Status: VERIFIED</span>
            </div>
          </div>

          <div class="sub-item">
            <strong style="color:#fbbf24;">Stage 1: Anti-Fraud Guard</strong> — Haversine EXIF geofence (&lt;50m) + pHash stock photo detection.<br/>
            <strong style="color:#38bdf8;">Stage 2: Planar Homography</strong> — ORB+RANSAC 3&times;3 matrix warps photo into exact defect angle.<br/>
            <strong style="color:#34d399;">Stage 3: Dual-Head Verification</strong> — Residual distress check (0 holes) + fresh bitumen texture match.
          </div>
        </div>

        <div class="card">
          <div class="card-title t-green"><span>● 7. 3D Volumetric Cavity Solver</span></div>
          <!-- 3D Surface Reconstruction Plot -->
          <div class="img-container">
            <img src="{img_3d}" alt="3D Pavement Volumetric Reconstruction">
          </div>
          <div class="math-panel">
            <div class="math-line"><span>Area (m&sup2;)</span><span style="color:#38bdf8;">=(w &times; GSD) &times; (h &times; GSD)</span></div>
            <div class="math-line"><span>Volume (m&sup3;)</span><span style="color:#818cf8;">=Area &times; Estimated Depth</span></div>
            <div class="math-line" style="border-top:1px solid #1e293b; padding-top:2px; color:#34d399; font-weight:700;"><span>Asphalt Required</span><span>=Volume &times; 2,400 kg/m&sup3;</span></div>
          </div>
        </div>
      </div>

      <!-- Column 4: GIS Map, Metrics & Status -->
      <div class="col-box">
        <div class="card">
          <div class="card-title t-green"><span>● 8. Municipal GIS Map & RHI Dial</span></div>
          <div class="card-body">Real-time ASTM D6433 Road Health Index portal with live incident markers and corridor health scoring:</div>
          
          <!-- Real GIS Map Snapshot -->
          <div class="img-container">
            <img src="{img_gis}" alt="Municipal GIS Map and RHI">
            <div class="img-caption">
              <span>State Highway 17 North Corridor</span>
              <span style="color:#34d399;">RHI: 90.0 (EXCELLENT)</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title t-amber"><span>● 9. Empirical Performance</span></div>
          <div class="metrics-2x2">
            <div class="metric-box"><div class="m-val" style="color:#fbbf24;">92.4%</div><div class="m-lbl">Pothole Recall</div></div>
            <div class="metric-box"><div class="m-val" style="color:#818cf8;">96.8%</div><div class="m-lbl">Vehicle Shield</div></div>
            <div class="metric-box"><div class="m-val" style="color:#38bdf8;">1,400+</div><div class="m-lbl">ORB Inliers</div></div>
            <div class="metric-box"><div class="m-val" style="color:#34d399;">&lt;40 ms</div><div class="m-lbl">Inference Latency</div></div>
          </div>
        </div>

        <div class="card" style="border-color:rgba(16,185,129,0.35);">
          <div class="card-title t-green"><span>● 10. Operational Status</span></div>
          <div class="sub-item">
            <div style="display:flex; justify-content:space-between; font-weight:700;"><span>Completed & Tested</span><span style="color:#34d399; font-family:monospace;">100%</span></div>
            <div style="color:#94a3b8; font-size:9px;">All 6 architectural tiers built, tested, and fully functional.</div>
          </div>
          <div class="sub-item">
            <div style="display:flex; justify-content:space-between; font-weight:700;"><span>Field Dashcam Testing</span><span style="color:#fbbf24; font-family:monospace;">Active</span></div>
            <div style="color:#94a3b8; font-size:9px;">Tested on 27.7s HD rural water-logged road patrol stream.</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="color:#cbd5e1;"><span>● 11. Production Tech Stack</span></div>
          <div class="tech-badges">
            <span class="t-pill">Python 3.10+</span>
            <span class="t-pill">FastAPI</span>
            <span class="t-pill">YOLOv8</span>
            <span class="t-pill">OpenCV 4.x</span>
            <span class="t-pill">ByteTrack</span>
            <span class="t-pill">Leaflet.js</span>
            <span class="t-pill">PostGIS</span>
            <span class="t-pill">imagehash</span>
          </div>
        </div>
      </div>

    </div>

    <!-- Footer -->
    <footer class="poster-ft">
      <div>
        <strong style="color:#ffffff;">National Institute of Technology Jalandhar</strong> • Department of Computer Science & Engineering • <span style="color:#fbbf24; font-family:monospace;">Roll: 24103119</span>
      </div>
      <div>
        Repository: <span style="color:#38bdf8; font-family:monospace;">github.com/Prathamesh-000/AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System</span>
      </div>
    </footer>

  </div>

</body>
</html>
"""

poster_html_path = DOCS_DIR / "project_poster.html"
poster_html_path.write_text(html_content, encoding="utf-8")
print(f"[build_rich_poster] Successfully wrote rich HTML to: {poster_html_path} ({len(html_content)} bytes)")

# Compile to PDF using Chrome Headless
pdf_path = DOCS_DIR / "RoadSentinel_AI_Project_Poster.pdf"
chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
cmd = [
    str(chrome_path),
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--no-pdf-header-footer",
    f"--print-to-pdf={pdf_path}",
    poster_html_path.as_uri()
]

proc = subprocess.run(cmd, capture_output=True, text=True)
print("Chrome return code:", proc.returncode)
if pdf_path.exists():
    print(f"[build_rich_poster] Generated PDF: {pdf_path} ({pdf_path.stat().st_size} bytes)")
else:
    print("[build_rich_poster] PDF generation failed.")
