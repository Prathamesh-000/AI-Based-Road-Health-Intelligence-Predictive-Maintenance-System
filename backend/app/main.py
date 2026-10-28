from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import PROJECT_NAME, VERSION, PHASE, API_PREFIX, STORAGE_DIR
from app.api.routes_detect import router as detect_router

app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="AI-Powered Road Health Intelligence - Phase 1: Video Ingestion, Telemetry Sync & Perception Engine"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local storage for evidence crops and uploads
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# Include Phase 1 Detection Router
app.include_router(detect_router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "phase": PHASE,
        "version": VERSION
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "project": PROJECT_NAME,
        "phase": PHASE,
        "docs_url": "/docs",
        "endpoints": {
            "detect_video": f"{API_PREFIX}/detect/video",
            "detect_image": f"{API_PREFIX}/detect/image"
        }
    }

