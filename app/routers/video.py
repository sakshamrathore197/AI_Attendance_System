import os
import shutil
import uuid
from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, BackgroundTasks, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import VideoSession
from app.services.video_service import analyze_video, get_processing_status

router = APIRouter()
templates = Jinja2Templates(directory="templates")

VIDEO_FOLDER = "static/uploads/video"
os.makedirs(VIDEO_FOLDER, exist_ok=True)

@router.get("/video/process")
def process_page(request: Request, db: Session = Depends(get_db)):
    recent_sessions = db.query(VideoSession).order_by(VideoSession.id.desc()).limit(10).all()
    today_str = str(date.today())
    return templates.TemplateResponse(
        "process_video.html",
        {
            "request": request,
            "page_title": "CCTV Video Processor",
            "sessions": recent_sessions,
            "today_date": today_str
        }
    )

@router.post("/video/process")
async def upload_and_process_video(
    background_tasks: BackgroundTasks,
    camera_name: str = Form(...),
    attendance_date: str = Form(...),
    direction: str = Form("IN"),
    video: UploadFile = File(...)
):
    if not video.filename:
        return {"status": False, "message": "No file uploaded."}

    session_id = str(uuid.uuid4())
    filename = f"{session_id[:8]}_{video.filename}"
    save_path = os.path.join(VIDEO_FOLDER, filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    # Launch processing in background so HTTP response is instant & non-blocking
    background_tasks.add_task(
        analyze_video,
        save_path,
        camera_name.strip(),
        attendance_date.strip(),
        session_id,
        direction.strip().upper()
    )

    return {
        "status": True,
        "message": f"Processing started for {direction.upper()} video '{video.filename}'.",
        "session_id": session_id,
        "camera_name": camera_name,
        "direction": direction.upper(),
        "attendance_date": attendance_date
    }

@router.get("/api/video/status/{session_id}")
def check_video_status(session_id: str):
    status_info = get_processing_status(session_id)
    return status_info

@router.get("/api/video/sessions")
def get_video_sessions_api(db: Session = Depends(get_db)):
    sessions = db.query(VideoSession).order_by(VideoSession.id.desc()).all()
    data = []
    for s in sessions:
        data.append({
            "id": s.id,
            "video_name": s.video_name,
            "camera_name": s.camera_name,
            "attendance_date": s.attendance_date,
            "total_frames": s.total_frames,
            "processed_frames": s.processed_frames,
            "recognized_faces": s.recognized_faces,
            "unknown_faces": s.unknown_faces,
            "processing_time": s.processing_time,
            "fps": s.fps,
            "status": s.status,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else ""
        })
    return {"success": True, "count": len(data), "data": data}