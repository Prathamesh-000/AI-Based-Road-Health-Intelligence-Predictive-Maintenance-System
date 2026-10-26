# RoadSentinel AI 🛣️🤖
### AI-Powered Road Health Intelligence, Spatial Telemetry & Automated Repair Verification System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/Deep%20Learning-PyTorch%20%7C%20YOLOv8-EE4C2C.svg)](https://pytorch.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%2B%20PostGIS-336791.svg)](https://postgis.net/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TailwindCSS-61DAFB.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Executive Summary

**RoadSentinel AI** is an end-to-end municipal road infrastructure intelligence platform designed to automate the complete lifecycle of road defect management: from **computer vision-based road distress detection** on moving vehicular footage, to **geospatial contractor assignment**, **anti-fraud repair submission**, and **AI-driven closed-loop repair verification**.

Traditional road inspection systems stop at detection. RoadSentinel AI bridges the operational gap between defect identification and verified remediation by introducing an automated verification engine that evaluates before-and-after repair evidence using homography alignment, defect residual inference, and telemetry integrity checks.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion & Preprocessing"]
        A[Dashcam Video Stream / MP4] --> B[Decodification & OpenCV Pipeline]
        T[GPX / Telemetry Metadata] --> C[Timestamped Telemetry Synchronizer]
    end

    subgraph Perception["2. AI Perception & Tracking Engine"]
        B --> D[YOLOv8 Multi-Distress Detector]
        D --> E[ByteTrack Multi-Object Tracker]
        E --> F[Single Best-Frame Extraction & Deduplication]
        F --> G[Monocular Depth & Volume Estimation]
    end

    subgraph Geospatial["3. Spatial Intelligence & Dispatch"]
        C & G --> H[PostGIS Spatial Query Engine]
        H --> I["Contractor Boundary Matching (ST_DWithin)"]
        I --> J[Incident Generation & Dynamic SLA Timer Engine]
        J --> K[Automated Dispatch & Notification Service]
    end

    subgraph Remediation["4. Contractor Remediation & Anti-Fraud"]
        K --> L[Contractor Web Portal]
        L --> M[Repair Evidence Submission: Before/After Photos]
        M --> N[Anti-Fraud Guard: EXIF Geofence + Perceptual Hash]
    end

    subgraph Verification["5. AI Closed-Loop Verification Engine"]
        N --> O[ORB/SIFT Homography & Perspective Alignment]
        O --> P[Secondary Defect Residual Inference]
        P --> Q[Fresh Bitumen / Patch Segmentation Check]
        Q --> R{Verification Decision Engine}
    end

    subgraph Outputs["6. Resolution & Public Transparency"]
        R -- Passed --> S[Status: VERIFIED & Contractor Scorecard Updated]
        R -- Incomplete --> U[Status: REWORK_REQUIRED & SLA Penalty Triggered]
        R -- Low Confidence --> V[Human-In-The-Loop (HITL) Admin Queue]
        S --> W[Public GIS Portal & Citizen Notification Feed]
    end
```

---

## 🚀 Key Engineering Pillars

### 1. Computer Vision & Distress Quantification
* **SOTA Object Detection:** Fine-tuned YOLOv8 model capable of classifying multiple pavement distress categories in compliance with **ASTM D6433 (Pavement Condition Index - PCI)**: Potholes, Alligator Cracking, Longitudinal/Transverse Cracks, and Depressions.
* **ByteTrack Multi-Object Tracking (MOT):** Overcomes frame-by-frame duplicate counts by associating bounding boxes across consecutive frames using Kalman filters and IoU distance matrices, selecting the single highest-resolution frame per unique defect.
* **Monocular Volumetric Severity Estimation:** Combines bounding box geometric metrics with monocular depth maps to approximate defect depth and volumetric displacement ($m^3$), outputting estimated asphalt tonnage for procurement.

### 2. Spatial Indexing & Contractor Orchestration
* **PostGIS Spatial Matching:** Ingests video telemetry (synchronized GPX/NMEA coordinates) and matches defect locations to active municipal road maintenance zones using spatial queries (`ST_Contains`, `ST_DWithin`, and spatial R-tree indexing).
* **Automated SLA Engine:** Evaluates visual severity and road classification (arterial vs. residential) to compute dynamic Service Level Agreement (SLA) deadlines (e.g., 24-hour critical window) with automated contractor notification dispatch.

### 3. Anti-Fraud & Closed-Loop AI Verification
* **Telemetry & Tamper Detection:** Extracts camera EXIF metadata, timestamp validity, and spatial geofences (verifying submission was photographed $\le 50\text{m}$ of incident site). Utilizes **Perceptual Hashing (pHash)** to block duplicate or recycled stock images.
* **Homography-Based Perspective Normalization:** Leverages ORB feature extraction and RANSAC-driven homography matrix transformation to warp the "after" repair image into the exact planar perspective of the "before" incident frame.
* **Residual Defect & Patch Validation:** Re-runs distress detection over the aligned repair region to ensure zero residual defect signatures while confirming patch boundary integration (fresh bitumen texture).

### 4. Enterprise Architecture & Public Governance
* **Asynchronous Microservices:** Built with **FastAPI** utilizing **Celery + Redis** message queues for offloading compute-heavy video ingestion, frame extraction, and PyTorch inference from API threads.
* **Human-in-the-Loop (HITL) Triage:** Outlier detections, occlusion edge cases, and contested contractor reworks route to a municipal engineer audit queue with visual heatmap explanations.
* **Public Transparency Portal:** Citizen dashboard featuring an interactive Mapbox/Leaflet heatmap displaying Road Health Index (RHI) scores, real-time repair progress, and before-and-after audit logs.

---

## 🛠️ Technology Stack

| Domain | Technologies |
| :--- | :--- |
| **Deep Learning & CV** | PyTorch, Ultralytics YOLOv8, ByteTrack, OpenCV, Depth Anything / MiDaS |
| **Backend & APIs** | Python 3.10+, FastAPI, Pydantic, Celery, Redis |
| **Database & GIS** | PostgreSQL 15, PostGIS, SQLAlchemy, GeoAlchemy2 |
| **Frontend & UI** | React 18, Tailwind CSS, Lucide Icons, Leaflet / Mapbox GL |
| **Security & Utilities** | PyExifTool, ImageHash (pHash), JWT Authentication, SMTP Mailer |
| **DevOps & Tooling** | Docker, Docker Compose, Git, Uvicorn |

---

## 📂 Project Structure

```text
AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System/
├── backend/
│   ├── app/
│   │   ├── api/             # REST endpoints (auth, incidents, contractors, verification)
│   │   ├── core/            # Config, security, database sessions
│   │   ├── models/          # SQLAlchemy & PostGIS ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── detection/   # YOLOv8 inference, ByteTrack, frame extractor
│   │   │   ├── telemetry/   # GPX/NMEA coordinate sync & interpolation
│   │   │   ├── verification/# Homography alignment, pHash, patch verification
│   │   │   └── notification/# Asynchronous email & webhook dispatchers
│   │   └── workers/         # Celery task definitions
│   ├── tests/               # Unit and integration test suites
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components (Heatmap, IncidentCard)
│   │   ├── pages/           # Contractor Dashboard, Public Portal, Admin HITL
│   │   └── services/        # Axios API client
│   └── package.json
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## ⚡ Quickstart & Installation

### Prerequisites
* Python 3.10+
* Node.js 18+
* PostgreSQL with PostGIS extension
* Redis

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/Prathamesh-000/AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System.git
cd AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

**RoadSentinel AI** is an end-to-end municipal road infrastructure intelligence platform designed to automate the complete lifecycle of road defect management: from **computer vision-based road distress detection** on moving vehicular footage, to **geospatial contractor assignment**, **anti-fraud repair submission**, and **AI-driven closed-loop repair verification**.

Traditional road inspection systems stop at detection. RoadSentinel AI bridges the operational gap between defect identification and verified remediation by introducing an automated verification engine that evaluates before-and-after repair evidence using homography alignment, defect residual inference, and telemetry integrity checks.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion & Preprocessing"]
        A[Dashcam Video Stream / MP4] --> B[Decodification & OpenCV Pipeline]
        T[GPX / Telemetry Metadata] --> C[Timestamped Telemetry Synchronizer]
    end

    subgraph Perception["2. AI Perception & Tracking Engine"]
        B --> D[YOLOv8 Multi-Distress Detector]
        D --> E[ByteTrack Multi-Object Tracker]
        E --> F[Single Best-Frame Extraction & Deduplication]
        F --> G[Monocular Depth & Volume Estimation]
    end

    subgraph Geospatial["3. Spatial Intelligence & Dispatch"]
        C & G --> H[PostGIS Spatial Query Engine]
        H --> I["Contractor Boundary Matching (ST_DWithin)"]
        I --> J[Incident Generation & Dynamic SLA Timer Engine]
        J --> K[Automated Dispatch & Notification Service]
    end

    subgraph Remediation["4. Contractor Remediation & Anti-Fraud"]
        K --> L[Contractor Web Portal]
        L --> M[Repair Evidence Submission: Before/After Photos]
        M --> N[Anti-Fraud Guard: EXIF Geofence + Perceptual Hash]
    end

    subgraph Verification["5. AI Closed-Loop Verification Engine"]
        N --> O[ORB/SIFT Homography & Perspective Alignment]
        O --> P[Secondary Defect Residual Inference]
        P --> Q[Fresh Bitumen / Patch Segmentation Check]
        Q --> R{Verification Decision Engine}
    end

    subgraph Outputs["6. Resolution & Public Transparency"]
        R -- Passed --> S[Status: VERIFIED & Contractor Scorecard Updated]
        R -- Incomplete --> U[Status: REWORK_REQUIRED & SLA Penalty Triggered]
        R -- Low Confidence --> V[Human-In-The-Loop (HITL) Admin Queue]
        S --> W[Public GIS Portal & Citizen Notification Feed]
    end
```

---

## 🚀 Key Engineering Pillars

### 1. Computer Vision & Distress Quantification
* **SOTA Object Detection:** Fine-tuned YOLOv8 model capable of classifying multiple pavement distress categories in compliance with **ASTM D6433 (Pavement Condition Index - PCI)**: Potholes, Alligator Cracking, Longitudinal/Transverse Cracks, and Depressions.
* **ByteTrack Multi-Object Tracking (MOT):** Overcomes frame-by-frame duplicate counts by associating bounding boxes across consecutive frames using Kalman filters and IoU distance matrices, selecting the single highest-resolution frame per unique defect.
* **Monocular Volumetric Severity Estimation:** Combines bounding box geometric metrics with monocular depth maps to approximate defect depth and volumetric displacement ($m^3$), outputting estimated asphalt tonnage for procurement.

### 2. Spatial Indexing & Contractor Orchestration
* **PostGIS Spatial Matching:** Ingests video telemetry (synchronized GPX/NMEA coordinates) and matches defect locations to active municipal road maintenance zones using spatial queries (`ST_Contains`, `ST_DWithin`, and spatial R-tree indexing).
* **Automated SLA Engine:** Evaluates visual severity and road classification (arterial vs. residential) to compute dynamic Service Level Agreement (SLA) deadlines (e.g., 24-hour critical window) with automated contractor notification dispatch.

### 3. Anti-Fraud & Closed-Loop AI Verification
* **Telemetry & Tamper Detection:** Extracts camera EXIF metadata, timestamp validity, and spatial geofences (verifying submission was photographed $\le 50\text{m}$ of incident site). Utilizes **Perceptual Hashing (pHash)** to block duplicate or recycled stock images.
* **Homography-Based Perspective Normalization:** Leverages ORB feature extraction and RANSAC-driven homography matrix transformation to warp the "after" repair image into the exact planar perspective of the "before" incident frame.
* **Residual Defect & Patch Validation:** Re-runs distress detection over the aligned repair region to ensure zero residual defect signatures while confirming patch boundary integration (fresh bitumen texture).

### 4. Enterprise Architecture & Public Governance
* **Asynchronous Microservices:** Built with **FastAPI** utilizing **Celery + Redis** message queues for offloading compute-heavy video ingestion, frame extraction, and PyTorch inference from API threads.
* **Human-in-the-Loop (HITL) Triage:** Outlier detections, occlusion edge cases, and contested contractor reworks route to a municipal engineer audit queue with visual heatmap explanations.
* **Public Transparency Portal:** Citizen dashboard featuring an interactive Mapbox/Leaflet heatmap displaying Road Health Index (RHI) scores, real-time repair progress, and before-and-after audit logs.

---

## 🛠️ Technology Stack

| Domain | Technologies |
| :--- | :--- |
| **Deep Learning & CV** | PyTorch, Ultralytics YOLOv8, ByteTrack, OpenCV, Depth Anything / MiDaS |
| **Backend & APIs** | Python 3.10+, FastAPI, Pydantic, Celery, Redis |
| **Database & GIS** | PostgreSQL 15, PostGIS, SQLAlchemy, GeoAlchemy2 |
| **Frontend & UI** | React 18, Tailwind CSS, Lucide Icons, Leaflet / Mapbox GL |
| **Security & Utilities** | PyExifTool, ImageHash (pHash), JWT Authentication, SMTP Mailer |
| **DevOps & Tooling** | Docker, Docker Compose, Git, Uvicorn |

---

## 📂 Project Structure

```text
AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System/
├── backend/
│   ├── app/
│   │   ├── api/             # REST endpoints (auth, incidents, contractors, verification)
│   │   ├── core/            # Config, security, database sessions
│   │   ├── models/          # SQLAlchemy & PostGIS ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── detection/   # YOLOv8 inference, ByteTrack, frame extractor
│   │   │   ├── telemetry/   # GPX/NMEA coordinate sync & interpolation
│   │   │   ├── verification/# Homography alignment, pHash, patch verification
│   │   │   └── notification/# Asynchronous email & webhook dispatchers
│   │   └── workers/         # Celery task definitions
│   ├── tests/               # Unit and integration test suites
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components (Heatmap, IncidentCard)
│   │   ├── pages/           # Contractor Dashboard, Public Portal, Admin HITL
│   │   └── services/        # Axios API client
│   └── package.json
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## ⚡ Quickstart & Installation

### Prerequisites
* Python 3.10+
* Node.js 18+
* PostgreSQL with PostGIS extension
* Redis

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/Prathamesh-000/AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System.git
cd AI-Based-Road-Health-Intelligence-Predictive-Maintenance-System
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

