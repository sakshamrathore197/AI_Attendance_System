from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models import Employee, Attendance, VideoSession, UnknownFace

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
@router.get("/dashboard")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "page_title": "Executive Dashboard"}
    )

@router.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    today_str = str(date.today())

    total_employees = db.query(Employee).filter(Employee.status == "Active").count()
    total_staff_all = db.query(Employee).count()

    today_attendance_count = db.query(func.count(func.distinct(Attendance.employee_id)))\
        .filter(Attendance.date == today_str).scalar() or 0

    attendance_pct = round((today_attendance_count / total_employees * 100), 1) if total_employees > 0 else 0

    total_videos_processed = db.query(VideoSession).count()
    total_unknown_faces = db.query(UnknownFace).filter(UnknownFace.status == "New").count()

    # Attendance trend (last 7 days)
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        day_str = str(day)
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

    # Recent Video Sessions
    recent_sessions_db = db.query(VideoSession).order_by(VideoSession.id.desc()).limit(5).all()
    recent_sessions = []
    for s in recent_sessions_db:
        recent_sessions.append({
            "id": s.id,
            "video_name": s.video_name,
            "camera_name": s.camera_name,
            "attendance_date": s.attendance_date,
            "recognized_faces": s.recognized_faces,
            "unknown_faces": s.unknown_faces,
            "status": s.status,
            "processing_time": s.processing_time,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else ""
        })

    # Recent Attendance Activity
    recent_attendance_db = db.query(Attendance).order_by(Attendance.id.desc()).limit(8).all()
    recent_attendance = []
    for a in recent_attendance_db:
        recent_attendance.append({
            "id": a.id,
            "employee_id": a.employee_id,
            "employee_name": a.employee_name,
            "date": a.date,
            "camera_name": a.camera_name,
            "status": a.status,
            "screenshot": a.screenshot
        })

    return {
        "success": True,
        "total_employees": total_employees,
        "total_staff_all": total_staff_all,
        "today_attendance": today_attendance_count,
        "attendance_percentage": attendance_pct,
        "total_videos_processed": total_videos_processed,
        "total_unknown_faces": total_unknown_faces,
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "dept_labels": dept_labels,
        "dept_data": dept_data,
        "recent_sessions": recent_sessions,
        "recent_attendance": recent_attendance
    }
