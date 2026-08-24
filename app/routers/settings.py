from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates

from app.services.settings_service import SettingsService

router = APIRouter(tags=["System Settings"])
templates = Jinja2Templates(directory="templates")


@router.get("/settings")
def settings_page(request: Request):
    settings = SettingsService.get_all()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page_title": "System Settings",
        "settings": settings
    })


@router.get("/api/settings")
def get_settings_api():
    return {"success": True, "settings": SettingsService.get_all()}


@router.post("/api/settings")
def update_settings_api(
    face_recognition_threshold: str = Form("0.60"),
    confirmation_frame_count: str = Form("4"),
    cooldown_duration: str = Form("45"),
    unknown_face_saving: str = Form("false"),
    screenshot_saving: str = Form("false"),
    rtsp_reconnect_interval: str = Form("10"),
    frame_processing_interval: str = Form("1"),
):
    new_settings = {
        "face_recognition_threshold": face_recognition_threshold,
        "confirmation_frame_count": confirmation_frame_count,
        "cooldown_duration": cooldown_duration,
        "unknown_face_saving": unknown_face_saving,
        "screenshot_saving": screenshot_saving,
        "rtsp_reconnect_interval": rtsp_reconnect_interval,
        "frame_processing_interval": frame_processing_interval,
    }
    SettingsService.update_all(new_settings)
    return {"success": True, "message": "System settings updated successfully.", "settings": SettingsService.get_all()}
