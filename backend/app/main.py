from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from app.core.config import PROJECT_NAME, VERSION, API_PREFIX, STORAGE_DIR, BASE_DIR
from app.api.routes_detect import router as detect_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_notifications import router as notifications_router
from app.api.routes_contractors import router as contractors_router
from app.api.routes_verification import router as verification_router

PHASE = "Phase 1 to 5 - Perception, Spatial Matching, Notification Dispatch, Contractor Portal & Closed-Loop AI Verification"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="AI-Powered Road Health Intelligence - Phase 5: Closed-Loop AI Verification & Anti-Fraud Engine"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local storage for evidence crops, uploads, and repairs
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# Mount static web directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Routers
app.include_router(detect_router, prefix=API_PREFIX)
app.include_router(incidents_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(contractors_router, prefix=API_PREFIX)
app.include_router(verification_router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "phase": PHASE,
        "version": VERSION
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def get_dashboard_html():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Contractor Dashboard</h1><p>Dashboard UI loading...</p>")


@app.get("/", tags=["System"])
async def root():
    return {
        "project": PROJECT_NAME,
        "phase": PHASE,
        "docs_url": "/docs",
        "dashboard_url": "/dashboard",
        "endpoints": {
            "detect_video": f"{API_PREFIX}/detect/video",
            "detect_image": f"{API_PREFIX}/detect/image",
            "list_incidents": f"{API_PREFIX}/incidents",
            "create_incident": f"{API_PREFIX}/incidents/create-from-detection",
            "list_notifications": f"{API_PREFIX}/notifications",
            "preview_notification": f"{API_PREFIX}/notifications/preview/{{incident_id}}",
            "dispatch_notification": f"{API_PREFIX}/notifications/dispatch/{{incident_id}}",
            "list_contractors": f"{API_PREFIX}/contractors",
            "contractor_queue": f"{API_PREFIX}/contractors/{{contractor_id}}/queue",
            "submit_repair": f"{API_PREFIX}/contractors/submit-repair",
            "verify_incident": f"{API_PREFIX}/verify/{{incident_id}}",
            "verification_report": f"{API_PREFIX}/verify/{{incident_id}}/report",
            "list_verification_reports": f"{API_PREFIX}/verify/reports",
            "evaluate_images": f"{API_PREFIX}/verify/evaluate-images"
        }
    }
