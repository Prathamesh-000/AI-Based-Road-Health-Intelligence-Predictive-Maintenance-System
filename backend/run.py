import uvicorn
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    print("\n========================================================")
    print(" 🚀 Launching RoadSentinel AI Platform")
    print(" 📡 Backend API & Web Portal: http://localhost:8000")
    print(" 📖 Interactive Swagger API Docs: http://localhost:8000/docs")
    print("========================================================\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
