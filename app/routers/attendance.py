import csv
import io
from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attendance, Employee

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/attendance")
def attendance_page(
    request: Request,
    date_val: Optional[str] = None,
    camera: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Attendance)
    if date_val:
        query = query.filter(Attendance.date == date_val)
    if camera:
        query = query.filter(Attendance.camera_name == camera)

    rows = query.order_by(Attendance.id.desc()).all()
    cameras = db.query(Attendance.camera_name).distinct().all()
    camera_list = [c[0] for c in cameras if c[0]]

    return templates.TemplateResponse(
        "attendance.html",
        {
            "request": request,
            "page_title": "Attendance Logs",
            "rows": rows,
            "cameras": camera_list,
            "selected_date": date_val or "",
            "selected_camera": camera or ""
        }
    )

@router.get("/api/attendance")
def get_attendance_api(
    query_str: Optional[str] = None,
    date_val: Optional[str] = None,
    camera: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Attendance)
    if query_str:
        pattern = f"%{query_str}%"
        q = q.filter((Attendance.employee_name.ilike(pattern)) | (Attendance.employee_id.ilike(pattern)))
    if date_val:
        q = q.filter(Attendance.date == date_val)
    if camera:
        q = q.filter(Attendance.camera_name == camera)
    if status:
        q = q.filter(Attendance.status == status)

    rows = q.order_by(Attendance.id.desc()).all()
    data = []
    for r in rows:
        data.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": r.employee_name,
            "date": r.date,
            "camera_name": r.camera_name,
            "first_seen": r.first_seen,
            "last_seen": r.last_seen,
            "total_frames": r.total_frames,
            "status": r.status,
            "screenshot": r.screenshot,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
        })

    return {"success": True, "count": len(data), "data": data}

@router.get("/api/attendance/export")
def export_attendance_csv(
    date_val: Optional[str] = None,
    camera: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Attendance)
    if date_val:
        query = query.filter(Attendance.date == date_val)
    if camera:
        query = query.filter(Attendance.camera_name == camera)

    records = query.order_by(Attendance.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Employee ID", "Employee Name", "Date", "Camera/Source", 
        "First Seen (s)", "Last Seen (s)", "Total Frames", "Status", "Timestamp"
    ])

    for r in records:
        writer.writerow([
            r.id, r.employee_id, r.employee_name, r.date, r.camera_name,
            r.first_seen, r.last_seen, r.total_frames, r.status,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        ])

    output.seek(0)
    filename = f"attendance_report_{date_val or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/api/attendance/mark-manual")
def mark_attendance_manual(
    employee_id: str = Form(...),
    attendance_date: str = Form(...),
    camera_name: str = Form("Manual Entry"),
    status: str = Form("Present"),
    db: Session = Depends(get_db)
):
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        return {"success": False, "message": f"Employee ID {employee_id} not found."}

    existing = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date == attendance_date,
        Attendance.camera_name == camera_name
    ).first()

    if existing:
        existing.status = status
        db.commit()
        return {"success": True, "message": f"Updated attendance for {emp.name}."}

    rec = Attendance(
        employee_id=emp.employee_id,
        employee_name=emp.name,
        date=attendance_date,
        camera_name=camera_name,
        first_seen=0.0,
        last_seen=0.0,
        total_frames=1,
        status=status,
        screenshot=""
    )
    db.add(rec)
    db.commit()

    return {"success": True, "message": f"Attendance marked for {emp.name} on {attendance_date}."}

@router.post("/api/attendance/delete")
def delete_attendance(id: int = Form(...), db: Session = Depends(get_db)):
    rec = db.query(Attendance).filter(Attendance.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(rec)
    db.commit()
    return {"success": True, "message": "Attendance record removed."}