import csv
import io
from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attendance, Employee, AttendanceSession, AttendanceEvent, AttendanceInterval

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def format_duration(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return "00:00:00"
    total_secs = int(seconds)
    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


@router.get("/attendance")
def attendance_page(
    request: Request,
    date_val: Optional[str] = None,
    db: Session = Depends(get_db)
):
    target_date = date_val or str(date.today())

    # Fetch daily session rollups
    daily_sessions = db.query(AttendanceSession).filter(AttendanceSession.date == target_date).order_by(AttendanceSession.id.desc()).all()

    # Fallback to Milestone 2 attendance table if no daily session records yet for that date
    legacy_rows = []
    if not daily_sessions:
        legacy_rows = db.query(Attendance).filter(Attendance.date == target_date).order_by(Attendance.id.desc()).all()

    # Get distinct dates for date picker
    dates = db.query(AttendanceSession.date).distinct().all()
    if not dates:
        dates = db.query(Attendance.date).distinct().all()
    date_list = [d[0] for d in dates if d[0]]
    if target_date not in date_list:
        date_list.append(target_date)
    date_list.sort(reverse=True)

    rows = []
    for s in daily_sessions:
        rows.append({
            "id": s.id,
            "employee_id": s.employee_id,
            "employee_name": s.employee_name,
            "date": s.date,
            "first_in": s.first_in or "—",
            "last_out": s.last_out or "—",
            "total_working_hours": format_duration(s.total_working_seconds),
            "total_working_seconds": s.total_working_seconds or 0.0,
            "status": s.current_status,
            "in_count": s.total_in_events,
            "out_count": s.total_out_events,
            "is_legacy": False
        })

    for r in legacy_rows:
        rows.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": r.employee_name,
            "date": r.date,
            "first_in": f"{int(r.first_seen)//60:02d}:{int(r.first_seen)%60:02d}",
            "last_out": f"{int(r.last_seen)//60:02d}:{int(r.last_seen)%60:02d}",
            "total_working_hours": format_duration(max(0, r.last_seen - r.first_seen)),
            "total_working_seconds": max(0, r.last_seen - r.first_seen),
            "status": r.status,
            "in_count": 1,
            "out_count": 1 if r.last_seen > r.first_seen else 0,
            "is_legacy": True
        })

    return templates.TemplateResponse(
        request=request,
        name="attendance.html",
        context={"page_title": "Daily Attendance Logs", "rows": rows, "available_dates": date_list, "selected_date": target_date}
    )



@router.get("/api/attendance/timeline/{employee_id}")
def get_employee_timeline_api(
    employee_id: str,
    date_val: Optional[str] = None,
    db: Session = Depends(get_db)
):
    target_date = date_val or str(date.today())
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    session_row = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.date == target_date
    ).first()

    events = db.query(AttendanceEvent).filter(
        AttendanceEvent.employee_id == employee_id,
        AttendanceEvent.event_date == target_date
    ).order_by(AttendanceEvent.id.asc()).all()

    intervals = db.query(AttendanceInterval).filter(
        AttendanceInterval.employee_id == employee_id,
        AttendanceInterval.date == target_date
    ).order_by(AttendanceInterval.id.asc()).all()

    events_data = [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "event_time": ev.event_time,
            "camera_id": ev.camera_id,
            "camera_name": ev.camera_name,
            "camera_location": ev.camera_location,
            "similarity_score": ev.similarity_score,
            "screenshot": ev.screenshot,
            "is_duplicate": ev.is_duplicate,
            "is_unexpected": ev.is_unexpected,
        }
        for ev in events
    ]

    intervals_data = [
        {
            "id": inv.id,
            "in_time": inv.in_time or "—",
            "out_time": inv.out_time or "Currently Inside",
            "duration": format_duration(inv.duration_seconds),
            "in_camera_id": inv.in_camera_id,
            "out_camera_id": inv.out_camera_id,
            "in_proof": inv.in_proof,
            "out_proof": inv.out_proof,
        }
        for inv in intervals
    ]

    return {
        "success": True,
        "employee_id": employee_id,
        "employee_name": emp.name if emp else (session_row.employee_name if session_row else employee_id),
        "department": emp.department if emp else "General",
        "date": target_date,
        "summary": {
            "first_in": session_row.first_in if session_row else None,
            "last_out": session_row.last_out if session_row else None,
            "total_working_hours": format_duration(session_row.total_working_seconds) if session_row else "00:00:00",
            "current_status": session_row.current_status if session_row else "Outside",
            "in_count": session_row.total_in_events if session_row else 0,
            "out_count": session_row.total_out_events if session_row else 0,
        },
        "events": events_data,
        "intervals": intervals_data,
    }


@router.get("/api/attendance/export")
def export_attendance_csv(
    date_val: Optional[str] = None,
    db: Session = Depends(get_db)
):
    target_date = date_val or str(date.today())
    sessions = db.query(AttendanceSession).filter(AttendanceSession.date == target_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Session ID", "Employee ID", "Employee Name", "Date",
        "First IN", "Last OUT", "Total Working Hours", "Total Working Seconds",
        "Current Status", "IN Count", "OUT Count"
    ])

    for s in sessions:
        writer.writerow([
            s.id, s.employee_id, s.employee_name, s.date,
            s.first_in or "", s.last_out or "", format_duration(s.total_working_seconds),
            round(s.total_working_seconds or 0, 1), s.current_status,
            s.total_in_events, s.total_out_events
        ])

    output.seek(0)
    filename = f"attendance_daily_{target_date}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )