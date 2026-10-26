import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from app.config import PROJECT_NAME, VERSION, API_PREFIX, STORAGE_DIR, BASE_DIR
from app.api.routes_detect import router as detect_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_contractors import router as contractors_router
from app.api.routes_public import router as public_router

app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="AI-Powered Road Health Intelligence, Spatial Telemetry & Automated Repair Verification Platform"
)

# Enable Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount media & evidence storage for direct browser rendering
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# Include Modular Routers
app.include_router(detect_router, prefix=API_PREFIX)
app.include_router(incidents_router, prefix=API_PREFIX)
app.include_router(contractors_router, prefix=API_PREFIX)
app.include_router(public_router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "version": VERSION
    }


# Static web client directory
WEB_DIR = BASE_DIR / "static"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def root_dashboard():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content=f"<h1>{PROJECT_NAME} v{VERSION}</h1><p>API is running. Access interactive docs at <a href='/docs'>/docs</a>.</p>")
