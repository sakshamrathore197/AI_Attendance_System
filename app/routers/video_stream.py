import os
import shutil
import uuid

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.video_service import (
    stream_rtsp_live,
    stream_uploaded_video,
    stream_webcam,
    stream_webcam_inout,
    request_stream_stop,
    get_processing_status,
)
from app.services.inout_engine import CAMERAS, InOutEngine, get_recent_events, get_camera
from app.services.camera_manager import CameraManager


router = APIRouter(prefix="/video", tags=["Live Video Streaming"])
templates = Jinja2Templates(directory="templates")

_inout_query = InOutEngine()
_LIVE_SESSIONS = {}

UPLOAD_FOLDER = "static/uploads/video"


@router.get("/live")
def live_video_page_redirect():
    return RedirectResponse(url="/video/process")


@router.get("/inout")
def live_inout_page_redirect():
    return RedirectResponse(url="/video/process")


# ---------------------------------------------------------------------------
# Option 1: Live CCTV RTSP (MediaMTX / FFmpeg / IP Cameras)
# ---------------------------------------------------------------------------
@router.post("/rtsp/prepare")
async def prepare_rtsp_stream(
    rtsp_url: str = Form(...),
    camera_name: str = Form("CCTV RTSP Camera"),
    direction: str = Form("IN"),
    attendance_date: str = Form(...),
):
    session_id = str(uuid.uuid4())
    _LIVE_SESSIONS[session_id] = {
        "mode": "rtsp",
        "rtsp_url": rtsp_url.strip(),
        "camera_name": camera_name.strip(),
        "direction": direction.strip().upper(),
        "attendance_date": attendance_date.strip(),
    }
    return {"status": True, "session_id": session_id}


@router.get("/rtsp/live/{session_id}")
def live_rtsp_stream(session_id: str):
    meta = _LIVE_SESSIONS.get(session_id)
    if not meta:
        return JSONResponse({"status": False, "message": "Unknown session_id. Call /video/rtsp/prepare first."}, status_code=404)

    return StreamingResponse(
        stream_rtsp_live(
            rtsp_url=meta["rtsp_url"],
            camera_name=meta["camera_name"],
            direction=meta.get("direction", "IN"),
            attendance_date=meta["attendance_date"],
            session_id=session_id
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ---------------------------------------------------------------------------
# Option 2: Uploaded Video (Live Preview Stream with IN/OUT selection)
# ---------------------------------------------------------------------------
@router.post("/stream/prepare")
async def prepare_live_upload(
    file: UploadFile = File(...),
    camera_name: str = Form(...),
    direction: str = Form("IN"),
    attendance_date: str = Form(...),
):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    session_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".mp4"
    saved_path = os.path.join(UPLOAD_FOLDER, f"{session_id}{ext}")

    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    _LIVE_SESSIONS[session_id] = {
        "mode": "upload",
        "video_path": saved_path,
        "camera_name": camera_name,
        "direction": direction.strip().upper(),
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
            video_path=meta["video_path"],
            camera_name=meta["camera_name"],
            direction=meta.get("direction", "IN"),
            attendance_date=meta["attendance_date"],
            session_id=session_id
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ---------------------------------------------------------------------------
# Option 3: Webcam Mode (Testing with IN/OUT toggle and instant release)
# ---------------------------------------------------------------------------
@router.post("/webcam/prepare")
async def prepare_webcam(
    camera_name: str = Form("Webcam Test"),
    direction: str = Form("IN"),
    attendance_date: str = Form(...),
    camera_index: int = Form(0),
):
    session_id = str(uuid.uuid4())
    _LIVE_SESSIONS[session_id] = {
        "mode": "webcam",
        "camera_index": camera_index,
        "camera_name": camera_name,
        "direction": direction.strip().upper(),
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
            camera_index=meta["camera_index"],
            camera_name=meta["camera_name"],
            direction=meta.get("direction", "IN"),
            attendance_date=meta["attendance_date"],
            session_id=session_id
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ---------------------------------------------------------------------------
# Connection Diagnostics & Testing Endpoint
# ---------------------------------------------------------------------------
@router.post("/test-connection")
def test_connection_endpoint(
    camera_type: str = Form("rtsp"),
    url_or_index: str = Form(...),
):
    """
    Tests an RTSP stream URL or Webcam index and returns connection status.
    """
    res = CameraManager.test_connection(camera_type, url_or_index)
    return res


# ---------------------------------------------------------------------------
# Universal Stream Controls
# ---------------------------------------------------------------------------
@router.post("/stream/stop/{session_id}")
@router.post("/webcam/stop/{session_id}")
@router.post("/rtsp/stop/{session_id}")
@router.post("/inout/stop/{session_id}")
def stop_universal_stream(session_id: str):
    request_stream_stop(session_id)
    _LIVE_SESSIONS.pop(session_id, None)
    return {"status": True, "message": "Stream stopped and hardware released successfully."}


@router.get("/stream/status/{session_id}")
@router.get("/rtsp/status/{session_id}")
@router.get("/webcam/status/{session_id}")
@router.get("/inout/status/{session_id}")
def stream_status(session_id: str):
    return get_processing_status(session_id)


# ---------------------------------------------------------------------------
# Side Panels & Event Queries
# ---------------------------------------------------------------------------
@router.get("/inout/cameras")
def list_inout_cameras():
    cameras = CameraManager.get_all_cameras()
    return {"status": True, "cameras": cameras}


@router.get("/inout/currently-inside")
def currently_inside():
    return {"status": True, "employees": _inout_query.get_currently_inside()}


@router.get("/inout/events")
def recent_events(limit: int = 20):
    return {"status": True, "events": get_recent_events(limit)}
