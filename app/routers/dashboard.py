from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from app.database import get_db
from app.models import Employee, Attendance, VideoSession, UnknownFace, AttendanceSession, AttendanceEvent, Camera
from app.services.inout_engine import InOutEngine, get_recent_events
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

inout_engine = InOutEngine()


@router.get("/")
@router.get("/dashboard")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"page_title": "Executive Dashboard"}
    )



@router.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    today_str = str(date.today())

    total_employees = db.query(Employee).filter(Employee.status == "Active").count()
    total_staff_all = db.query(Employee).count()

    # Present Today: employees with session row or attendance row today
    present_today = db.query(func.count(func.distinct(AttendanceSession.employee_id)))\
        .filter(AttendanceSession.date == today_str).scalar() or 0
    if present_today == 0:
        present_today = db.query(func.count(func.distinct(Attendance.employee_id)))\
            .filter(Attendance.date == today_str).scalar() or 0

    attendance_pct = round((present_today / total_employees * 100), 1) if total_employees > 0 else 0

    currently_inside_rows = inout_engine.get_currently_inside()
    currently_inside_count = len(currently_inside_rows)
    currently_outside_count = max(0, total_employees - currently_inside_count)

    in_events_today = db.query(AttendanceEvent).filter(
        AttendanceEvent.event_date == today_str,
        AttendanceEvent.event_type == "IN",
        AttendanceEvent.is_duplicate == 0
    ).count()

    out_events_today = db.query(AttendanceEvent).filter(
        AttendanceEvent.event_date == today_str,
        AttendanceEvent.event_type == "OUT",
        AttendanceEvent.is_duplicate == 0
    ).count()

    total_videos_processed = db.query(VideoSession).count()
    total_unknown_faces = db.query(UnknownFace).filter(UnknownFace.status == "New").count()

    active_cameras = db.query(Camera).filter(Camera.status == "Connected").count()
    camera_errors = db.query(Camera).filter(Camera.status == "Error").count()
    total_cameras = db.query(Camera).count()

    # Attendance trend (last 7 days)
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        day_str = str(day)
        count = db.query(func.count(func.distinct(AttendanceSession.employee_id)))\
            .filter(AttendanceSession.date == day_str).scalar() or 0
        if count == 0:
            count = db.query(func.count(func.distinct(Attendance.employee_id)))\
                .filter(Attendance.date == day_str).scalar() or 0
        trend_labels.append(day.strftime("%b %d"))
        trend_data.append(count)

    # Department Breakdown
    dept_counts = db.query(Employee.department, func.count(Employee.id))\
        .filter(Employee.status == "Active")\
        .group_by(Employee.department).all()

    dept_labels = [dept if dept else "General" for dept, _ in dept_counts]
    dept_data = [count for _, count in dept_counts]

    # Recent Attendance Events / Activity
    recent_events = get_recent_events(10)
    if not recent_events:
        recent_attendance_db = db.query(Attendance).order_by(Attendance.id.desc()).limit(8).all()
        recent_events = [
            {
                "employee_id": a.employee_id,
                "employee_name": a.employee_name,
                "event_type": "IN",
                "event_date": a.date,
                "event_time": f"{int(a.first_seen)//60:02d}:{int(a.first_seen)%60:02d}",
                "camera_name": a.camera_name,
            }
            for a in recent_attendance_db
        ]

    # Camera status breakdown
    cameras_db = db.query(Camera).all()
    camera_list = [
        {
            "id": c.camera_id,
            "name": c.camera_name,
            "direction": c.direction,
            "status": c.status,
            "location": c.location,
            "fps": c.fps or 0,
        }
        for c in cameras_db
    ]

    return {
        "success": True,
        "total_employees": total_employees,
        "total_staff_all": total_staff_all,
        "today_attendance": present_today,
        "attendance_percentage": attendance_pct,
        "currently_inside": currently_inside_count,
        "currently_outside": currently_outside_count,
        "in_events_today": in_events_today,
        "out_events_today": out_events_today,
        "total_videos_processed": total_videos_processed,
        "total_unknown_faces": total_unknown_faces,
        "active_cameras": active_cameras,
        "camera_errors": camera_errors,
        "total_cameras": total_cameras,
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "dept_labels": dept_labels,
        "dept_data": dept_data,
        "currently_inside_list": currently_inside_rows,
        "recent_events": recent_events,
        "cameras": camera_list,
    }

