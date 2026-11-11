import uvicorn
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" 🚀 Launching RoadSentinel AI - Complete Municipal Platform (Phases 1-6)")
    print(" 📡 Backend API Root:              http://127.0.0.1:8000")
    print(" 📖 Interactive Swagger API Docs: http://127.0.0.1:8000/docs")
    print(" 🌐 Civic GIS Transparency Portal: http://127.0.0.1:8000/public")
    print(" 👷 Contractor Remediation Portal: http://127.0.0.1:8000/dashboard")
    print(" 🗺️ Live GeoJSON Hazards Feed:     http://127.0.0.1:8000/api/v1/public/hazards")
    print("="*70 + "\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

