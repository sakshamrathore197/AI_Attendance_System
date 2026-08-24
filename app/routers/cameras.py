from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.camera_manager import CameraManager

router = APIRouter(tags=["Camera Management"])
templates = Jinja2Templates(directory="templates")


@router.get("/cameras")
def cameras_page(request: Request):
    cameras = CameraManager.get_all_cameras()
    return templates.TemplateResponse("cameras.html", {
        "request": request,
        "page_title": "Camera Management",
        "cameras": cameras
    })


@router.get("/api/cameras")
def get_cameras_api():
    cameras = CameraManager.get_all_cameras()
    return {"success": True, "count": len(cameras), "cameras": cameras}


@router.post("/api/cameras")
def add_camera_api(
    camera_id: str = Form(...),
    camera_name: str = Form(...),
    camera_type: str = Form("webcam"),
    url_or_index: str = Form("0"),
    location: str = Form("General Area"),
    direction: str = Form("IN"),
):
    res = CameraManager.create_camera({
        "camera_id": camera_id,
        "camera_name": camera_name,
        "camera_type": camera_type,
        "url_or_index": url_or_index,
        "location": location,
        "direction": direction,
    })
    if not res["status"]:
        return JSONResponse(res, status_code=400)
    return res


@router.put("/api/cameras/{camera_id}")
async def update_camera_api(camera_id: str, request: Request):
    data = await request.json()
    res = CameraManager.update_camera(camera_id, data)
    if not res["status"]:
        return JSONResponse(res, status_code=400)
    return res


@router.delete("/api/cameras/{camera_id}")
def delete_camera_api(camera_id: str):
    res = CameraManager.delete_camera(camera_id)
    if not res["status"]:
        return JSONResponse(res, status_code=400)
    return res


@router.post("/api/cameras/test")
def test_camera_api(
    camera_type: str = Form("webcam"),
    url_or_index: str = Form("0"),
):
    res = CameraManager.test_connection(camera_type, url_or_index)
    return res
