from datetime import datetime, date
from app.database import SessionLocal
from app.models import Attendance


class AttendanceManager:
    def __init__(self, camera_name: str = None, attendance_date: str = None):
        self.records = {}
        if attendance_date:
            self.load_existing(attendance_date)

    def load_existing(self, attendance_date: str):
        """
        Preload everyone already marked present today, across ALL cameras.
        These are kept only as reference (seen_this_session=False) so that,
        if the same person is later re-detected in this run, we know their
        true original first_seen/screenshot instead of resetting them.
        Rows that are never re-detected in this session are NOT written
        back to the DB (see get_records()).
        """
        db = SessionLocal()
        try:
            existing_records = db.query(Attendance).filter(
                Attendance.date == attendance_date
            ).all()

            for rec in existing_records:
                self.records[rec.employee_id] = {
                    "employee_id": rec.employee_id,
                    "name": rec.employee_name,
                    "first_seen": rec.first_seen,
                    "last_seen": rec.last_seen,
                    "frames": rec.total_frames or 1,
                    "status": rec.status or "Present",
                    "screenshot": rec.screenshot or "",
                    "seen_this_session": False,
                }
        except Exception as e:
            print(f"Error loading existing attendance: {e}")
        finally:
            db.close()

    def mark(self, employee, frame_no, fps, screenshot_filename=""):
        timestamp = round(frame_no / fps, 2) if fps > 0 else 0.0
        emp_id = employee["employee_id"]

        prior = self.records.get(emp_id)

        if not prior or not prior.get("seen_this_session"):

            self.records[emp_id] = {
                "employee_id": emp_id,
                "name": employee["name"],
                "first_seen": prior["first_seen"] if prior else timestamp,
                "last_seen": timestamp,
                "frames": 1,
                "status": "Present",
                "screenshot": (prior["screenshot"] if prior and prior.get("screenshot") else None)
                              or screenshot_filename or f"{emp_id}_{frame_no}.jpg",
                "seen_this_session": True,
            }
            if prior:
                print(f"🔁 Re-detected (different session/camera): {emp_id} - {employee['name']}")
            else:
                print(f"✅ Attendance Marked: {emp_id} - {employee['name']}")
        else:
            # Same person seen again within this same processing run.
            if timestamp > self.records[emp_id]["last_seen"]:
                self.records[emp_id]["last_seen"] = timestamp
            self.records[emp_id]["frames"] += 1
            if screenshot_filename and not self.records[emp_id]["screenshot"]:
                self.records[emp_id]["screenshot"] = screenshot_filename

    def get_records(self):
        return [r for r in self.records.values() if r.get("seen_this_session")]

    def save(self, camera_name, attendance_date):
        db = SessionLocal()
        try:
            for record in self.get_records():
                existing = db.query(Attendance).filter(
                    Attendance.employee_id == record["employee_id"],
                    Attendance.date == attendance_date
                ).first()

                if existing:
                    
                    existing.last_seen = record["last_seen"]
                    existing.camera_name = camera_name
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
