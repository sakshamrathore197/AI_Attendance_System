from sqlalchemy import Column, Integer, String, Float, DateTime,ForeignKey,LargeBinary
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)

    employee_id = Column(String, unique=True, index=True)

    name = Column(String)

    department = Column(String)

    designation = Column(String)

    mobile = Column(String)

    email = Column(String)

    status = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

    images = relationship(
        "EmployeeImage",
        back_populates="employee",
        cascade="all, delete"
    )


class EmployeeImage(Base):
    __tablename__ = "employee_images"

    id = Column(Integer, primary_key=True)

    employee_ref = Column(Integer, ForeignKey("employees.id"))

    image_path = Column(String)

    embedding = Column(LargeBinary)

    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship(
        "Employee",
        back_populates="images"
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)

    employee_id = Column(String)

    employee_name = Column(String)

    date = Column(String)

    camera_name = Column(String)

    first_seen = Column(Float)

    last_seen = Column(Float)

    total_frames = Column(Integer)

    status = Column(String)

    screenshot = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)


class UnknownFace(Base):
    __tablename__ = "unknown_faces"

    id = Column(Integer, primary_key=True)

    timestamp = Column(String)

    frame_number = Column(Integer)

    confidence = Column(Float)

    image_path = Column(String)

    status = Column(String, default="New")

    created_at = Column(DateTime, default=datetime.utcnow)

class VideoSession(Base):
    __tablename__ = "video_sessions"

    id = Column(Integer, primary_key=True)

    video_name = Column(String)
    camera_name = Column(String)

    attendance_date = Column(String)

    total_frames = Column(Integer)

    processed_frames = Column(Integer)

    recognized_faces = Column(Integer)

    unknown_faces = Column(Integer)

    processing_time = Column(Float)

    fps = Column(Float)

    status = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)