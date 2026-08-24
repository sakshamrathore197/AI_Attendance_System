from sqlalchemy import Column, Integer, String, Float, DateTime,ForeignKey,LargeBinary,UniqueConstraint
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

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
    )

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

    frame_number = Column(Integer, nullable=True)

    confidence = Column(Float, nullable=True)

    image_path = Column(String)

    camera_id = Column(String, nullable=True)

    camera_name = Column(String, nullable=True)

    first_seen = Column(String, nullable=True)

    last_seen = Column(String, nullable=True)

    seen_count = Column(Integer, default=1)

    status = Column(String, default="New")

    created_at = Column(DateTime, default=datetime.utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True)

    camera_id = Column(String, unique=True, index=True)

    camera_name = Column(String)

    camera_type = Column(String, default="webcam")  # webcam | rtsp | upload

    url_or_index = Column(String)  # "0", "1", or "rtsp://..."

    location = Column(String, nullable=True)

    direction = Column(String, default="IN")  # IN | OUT | General

    status = Column(String, default="Disconnected")  # Connected | Disconnected | Error

    last_connected_time = Column(String, nullable=True)

    last_error = Column(String, nullable=True)

    is_active = Column(Integer, default=1)

    fps = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)

    value = Column(String)

    description = Column(String, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

    output_video_path = Column(String, nullable=True)

    source_type = Column(String, default="upload")

    created_at = Column(DateTime, default=datetime.utcnow)


# Recognition-confirmation + IN/OUT engine

class AttendanceEvent(Base):
    """A single confirmed IN or OUT event for one employee on one camera."""
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True)

    employee_id = Column(String, index=True)
    employee_name = Column(String)

    event_type = Column(String)   # "IN" | "OUT"
    event_date = Column(String, index=True)   # "YYYY-MM-DD"
    event_time = Column(String)               # "HH:MM:SS"

    camera_id = Column(String, index=True)
    camera_name = Column(String)
    camera_location = Column(String, nullable=True)

    similarity_score = Column(Float)
    screenshot = Column(String, nullable=True)

    source_type = Column(String, default="webcam")   # webcam | rtsp | upload
    session_id = Column(String, nullable=True)

    is_duplicate = Column(Integer, default=0)     # 1 if suppressed by cooldown (logged, not acted on)
    is_unexpected = Column(Integer, default=0)    # 1 if OUT-without-IN or IN-while-inside

    created_at = Column(DateTime, default=datetime.utcnow)


class AttendanceInterval(Base):
    """One IN -> OUT span for an employee on a given day."""
    __tablename__ = "attendance_intervals"

    id = Column(Integer, primary_key=True)

    employee_id = Column(String, index=True)
    date = Column(String, index=True)

    in_time = Column(String, nullable=True)     # "HH:MM:SS"
    out_time = Column(String, nullable=True)    # null while still inside

    duration_seconds = Column(Float, default=0.0)

    in_camera_id = Column(String, nullable=True)
    out_camera_id = Column(String, nullable=True)

    in_proof = Column(String, nullable=True)
    out_proof = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class AttendanceSession(Base):
    """One row per employee per day — the daily rollup."""
    __tablename__ = "attendance_daily"

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_daily_employee_date"),
    )

    id = Column(Integer, primary_key=True)

    employee_id = Column(String, index=True)
    employee_name = Column(String)
    date = Column(String, index=True)

    first_in = Column(String, nullable=True)
    last_out = Column(String, nullable=True)

    total_in_events = Column(Integer, default=0)
    total_out_events = Column(Integer, default=0)

    total_working_seconds = Column(Float, default=0.0)

    current_status = Column(String, default="Outside")   # Outside | Inside | Completed

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)