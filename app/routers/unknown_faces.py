from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import UnknownFace, Employee, EmployeeImage, Attendance
from app.face_engine import validate_face
import os
import shutil
import numpy as np

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/unknown-faces")
def unknown_faces_page(request: Request, db: Session = Depends(get_db)):
    faces = db.query(UnknownFace).order_by(UnknownFace.id.desc()).all()
    employees = db.query(Employee).filter(Employee.status == "Active").all()
    
    return templates.TemplateResponse(
        request=request,
        name="unknown_faces.html",
        context={"page_title": "Unknown Face Detections", "faces": faces, "employees": employees}
    )


@router.get("/api/unknown-faces")
def get_unknown_faces_api(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(UnknownFace)
    if status:
        q = q.filter(UnknownFace.status == status)
    
    faces = q.order_by(UnknownFace.id.desc()).all()
    data = []
    for f in faces:
        data.append({
            "id": f.id,
            "timestamp": f.timestamp,
            "frame_number": f.frame_number,
            "confidence": f.confidence,
            "image_path": f.image_path,
            "status": f.status,
            "created_at": f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else ""
        })
    return {"success": True, "count": len(data), "data": data}

@router.post("/api/unknown-faces/assign")
def assign_unknown_face(
    face_id: int = Form(...),
    employee_id: str = Form(...),
    db: Session = Depends(get_db)
):
    unk_face = db.query(UnknownFace).filter(UnknownFace.id == face_id).first()
    if not unk_face:
        return {"success": False, "message": "Unknown face entry not found."}

    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        return {"success": False, "message": f"Employee {employee_id} not found."}

    img_full_path = os.path.join("static/uploads/unknown_faces", unk_face.image_path)
    
    if os.path.exists(img_full_path):
        # Extract face embedding and save to employee
        status_val, embedding = validate_face(img_full_path)
        if embedding is not None:
            emp_folder = f"static/uploads/employees/{emp.employee_id}"
            os.makedirs(emp_folder, exist_ok=True)
            target_path = os.path.join(emp_folder, f"assigned_{unk_face.image_path}")
            shutil.copyfile(img_full_path, target_path)

            embedding_bytes = embedding.astype(np.float32).tobytes()
            db.add(EmployeeImage(
                employee_ref=emp.id,
                image_path=target_path,
                embedding=embedding_bytes
            ))

    unk_face.status = f"Assigned ({emp.employee_id})"
    db.commit()

    return {"success": True, "message": f"Face assigned to {emp.name} ({emp.employee_id})."}
