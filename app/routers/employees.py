import os
import shutil
import numpy as np
from typing import List, Optional
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Employee, EmployeeImage, Attendance
from app.face_engine import validate_face
from app.services.embedding_service import clear_embedding_cache

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/employees")
def employees_page(request: Request, db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.id.desc()).all()
    departments = db.query(Employee.department).distinct().all()
    dept_list = [d[0] for d in departments if d[0]]
    
    # Calculate stats per employee
    emp_data = []
    for emp in employees:
        img_count = len(emp.images)
        first_img = emp.images[0].image_path if img_count > 0 else ""
        emp_data.append({
            "id": emp.id,
            "employee_id": emp.employee_id,
            "name": emp.name,
            "department": emp.department or "General",
            "designation": emp.designation or "-",
            "mobile": emp.mobile or "-",
            "email": emp.email or "-",
            "status": emp.status or "Active",
            "image_count": img_count,
            "avatar": first_img,
            "created_at": emp.created_at.strftime("%Y-%m-%d") if emp.created_at else ""
        })

    return templates.TemplateResponse(
        "employees.html",
        {
            "request": request,
            "page_title": "Employee Directory",
            "employees": emp_data,
            "departments": dept_list
        }
    )

@router.get("/employees/add")
def employee_add_page(request: Request):
    return templates.TemplateResponse(
        "add_employee.html",
        {"request": request, "page_title": "Add New Employee"}
    )

@router.get("/api/employees")
def get_employees_api(
    query: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Employee)
    if query:
        search_pattern = f"%{query}%"
        q = q.filter(
            (Employee.name.ilike(search_pattern)) | 
            (Employee.employee_id.ilike(search_pattern)) | 
            (Employee.department.ilike(search_pattern))
        )
    if department:
        q = q.filter(Employee.department == department)
    if status:
        q = q.filter(Employee.status == status)

    employees = q.order_by(Employee.id.desc()).all()
    result = []
    for emp in employees:
        first_img = emp.images[0].image_path if len(emp.images) > 0 else ""
        result.append({
            "id": emp.id,
            "employee_id": emp.employee_id,
            "name": emp.name,
            "department": emp.department,
            "designation": emp.designation,
            "mobile": emp.mobile,
            "email": emp.email,
            "status": emp.status,
            "image_count": len(emp.images),
            "avatar": first_img
        })
    return {"success": True, "count": len(result), "data": result}

@router.post("/employees/add")
async def add_employee_submit(
    employee_id: str = Form(...),
    name: str = Form(...),
    department: str = Form(""),
    designation: str = Form(""),
    mobile: str = Form(""),
    email: str = Form(""),
    status: str = Form("Active"),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Check duplicate ID
        existing = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if existing:
            return {"status": "failed", "message": f"Employee ID '{employee_id}' already exists."}

        if not images or len(images) < 1:
            return {"status": "failed", "message": "At least 1 valid face image is required."}

        # Create Employee object
        employee = Employee(
            employee_id=employee_id.strip(),
            name=name.strip(),
            department=department.strip() or "General",
            designation=designation.strip() or "Staff",
            mobile=mobile.strip(),
            email=email.strip(),
            status=status.strip()
        )
        db.add(employee)
        db.flush()

        employee_folder = f"static/uploads/employees/{employee_id}"
        os.makedirs(employee_folder, exist_ok=True)

        uploaded = 0
        no_face = []
        multiple_faces = []

        for img in images:
            if not img.filename:
                continue

            save_path = os.path.join(employee_folder, img.filename)
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)

            face_status, embedding = validate_face(save_path)

            if face_status == "NO_FACE":
                if os.path.exists(save_path):
                    os.remove(save_path)
                no_face.append(img.filename)
                continue
            elif face_status == "MULTIPLE_FACES":
                if os.path.exists(save_path):
                    os.remove(save_path)
                multiple_faces.append(img.filename)
                continue

            embedding_bytes = embedding.astype(np.float32).tobytes()
            emp_img = EmployeeImage(
                employee_ref=employee.id,
                image_path=save_path,
                embedding=embedding_bytes
            )
            db.add(emp_img)
            uploaded += 1

        if uploaded == 0:
            shutil.rmtree(employee_folder, ignore_errors=True)
            db.rollback()
            return {
                "status": "failed",
                "message": "No valid faces detected in uploaded images. Please ensure photos are clear.",
                "no_face": no_face,
                "multiple_faces": multiple_faces
            }

        db.commit()
        clear_embedding_cache()

        return {
            "status": "success",
            "message": f"Employee {name} ({employee_id}) successfully registered with {uploaded} face profile(s).",
            "employee_id": employee_id,
            "embeddings_created": uploaded,
            "no_face": no_face,
            "multiple_faces": multiple_faces
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@router.post("/api/employees/{emp_id}/delete")
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == emp_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_folder = f"static/uploads/employees/{employee.employee_id}"
    if os.path.exists(employee_folder):
        shutil.rmtree(employee_folder, ignore_errors=True)

    db.delete(employee)
    db.commit()
    clear_embedding_cache()

    return {"success": True, "message": f"Employee {employee.name} deleted."}
