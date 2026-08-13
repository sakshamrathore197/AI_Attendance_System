import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse

from app.services.video_service import (
    stream_uploaded_video,
    stream_webcam,
    request_stream_stop,
    get_processing_status,
)

router = APIRouter(prefix="/video", tags=["Live Video Streaming"])


@router.get("/live")
def live_video_page_redirect():
    # The live-stream / webcam UI now lives inside /video/process
    return RedirectResponse(url="/video/process")


_LIVE_SESSIONS = {}

UPLOAD_FOLDER = "static/uploads/video"

@router.post("/stream/prepare")
async def prepare_live_upload(
    file: UploadFile = File(...),
    camera_name: str = Form(...),
    attendance_date: str = Form(...),
):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    session_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".mp4"
    saved_path = os.path.join(UPLOAD_FOLDER, f"{session_id}{ext}")

    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    _LIVE_SESSIONS[session_id] = {
        "video_path": saved_path,
        "camera_name": camera_name,
        "attendance_date": attendance_date,
    }

    return {"status": True, "session_id": session_id}


@router.get("/stream/live/{session_id}")
def live_upload_stream(session_id: str):
    meta = _LIVE_SESSIONS.get(session_id)
    if not meta:
        return JSONResponse({"status": False, "message": "Unknown session_id. Call /video/stream/prepare first."}, status_code=404)

    return StreamingResponse(
        stream_uploaded_video(
            meta["video_path"], meta["camera_name"], meta["attendance_date"], session_id
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/webcam/prepare")
async def prepare_webcam(
    camera_name: str = Form(...),
    attendance_date: str = Form(...),
    camera_index: int = Form(0),
):
    session_id = str(uuid.uuid4())
    _LIVE_SESSIONS[session_id] = {
        "camera_index": camera_index,
        "camera_name": camera_name,
        "attendance_date": attendance_date,
    }
    return {"status": True, "session_id": session_id}


@router.get("/webcam/live/{session_id}")
def live_webcam_stream(session_id: str):
    meta = _LIVE_SESSIONS.get(session_id)
    if not meta:
        return JSONResponse({"status": False, "message": "Unknown session_id. Call /video/webcam/prepare first."}, status_code=404)

    return StreamingResponse(
        stream_webcam(
            meta["camera_index"], meta["camera_name"], meta["attendance_date"], session_id
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )



@router.post("/stream/stop/{session_id}")
def stop_stream(session_id: str):
    request_stream_stop(session_id)
    _LIVE_SESSIONS.pop(session_id, None)
    return {"status": True, "message": "Stop signal sent."}


@router.get("/stream/status/{session_id}")
def stream_status(session_id: str):
    return get_processing_status(session_id)
