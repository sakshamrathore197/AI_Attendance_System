import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.storage import init_db
import app.models
# Initialize Database tables
init_db()

# Create required upload folders
os.makedirs("static/uploads/employees", exist_ok=True)
os.makedirs("static/uploads/video", exist_ok=True)
os.makedirs("static/uploads/unknown_faces", exist_ok=True)
os.makedirs("static/screenshots", exist_ok=True)
os.makedirs("static/processed_videos", exist_ok=True)

app = FastAPI(
    title="AI CCTV Video Attendance System",
    description="Automated AI-powered Face Recognition Attendance System using CCTV Video Streams",
    version="2.0.0"
)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Import APIRouters
from app.routers.dashboard import router as dashboard_router
from app.routers.employees import router as employees_router
from app.routers.attendance import router as attendance_router
from app.routers.video import router as video_router
from app.routers.unknown_faces import router as unknown_faces_router
from app.routers.video_stream import router as video_stream_router
from app.routers.cameras import router as cameras_router
from app.routers.settings import router as settings_router

# Include routers
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(attendance_router)
app.include_router(video_router)
app.include_router(unknown_faces_router)
app.include_router(video_stream_router)
app.include_router(cameras_router)
app.include_router(settings_router)