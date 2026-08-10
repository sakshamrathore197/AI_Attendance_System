from datetime import datetime, date
from app.database import SessionLocal
from app.models import Attendance

class AttendanceManager:
    def __init__(self):
        self.records = {}

    def mark(self, employee, frame_no, fps, screenshot_filename=""):
        timestamp = frame_no / fps if fps > 0 else 0.0

        emp_id = employee["employee_id"]
        if emp_id not in self.records:
            self.records[emp_id] = {
                "employee_id": emp_id,
                "name": employee["name"],
                "first_seen": round(timestamp, 2),
                "last_seen": round(timestamp, 2),
                "frames": 1,
                "status": "Present",
                "screenshot": screenshot_filename or f"{emp_id}_{frame_no}.jpg"
            }
            print(f"✅ Attendance Marked: {emp_id} - {employee['name']}")
        else:
            self.records[emp_id]["last_seen"] = round(timestamp, 2)
            self.records[emp_id]["frames"] += 1
            if screenshot_filename and not self.records[emp_id]["screenshot"]:
                self.records[emp_id]["screenshot"] = screenshot_filename

    def get_records(self):
        return list(self.records.values())

    def save(self, camera_name, attendance_date):
        db = SessionLocal()
        try:
            for record in self.records.values():
                existing = db.query(Attendance).filter(
                    Attendance.employee_id == record["employee_id"],
                    Attendance.date == attendance_date,
                    Attendance.camera_name == camera_name
                ).first()
                if existing:
                    existing.last_seen = record["last_seen"]
                    existing.total_frames = record["frames"]
                    if record["screenshot"] and not existing.screenshot:
                        existing.screenshot = record["screenshot"]
                else:
                    db.add(
                        Attendance(
                            employee_id=record["employee_id"],
                            employee_name=record["name"],
                            date=attendance_date,
                            camera_name=camera_name,
                            first_seen=record["first_seen"],
                            last_seen=record["last_seen"],
                            total_frames=record["frames"],
                            status=record["status"],
                            screenshot=record["screenshot"]
                        )
                    )
            db.commit()
        except Exception as e:
            print(f"Error saving attendance: {e}")
            db.rollback()
        finally:
            db.close()