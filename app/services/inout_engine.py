import time
from datetime import datetime

from app.database import SessionLocal
from app.models import AttendanceEvent, AttendanceInterval, AttendanceSession, Employee, Attendance
from app.services.camera_manager import CameraManager
from app.services.settings_service import SettingsService


class MovementState:
    WAITING = "Waiting"
    IN = "IN"
    OUT = "OUT"


CAMERAS = {
    "webcam-in": {
        "camera_id": "webcam-in",
        "camera_name": "Webcam - Entrance",
        "camera_index": 0,
        "direction": "IN",
        "location": "Main Entrance",
    },
    "webcam-out": {
        "camera_id": "webcam-out",
        "camera_name": "Webcam - Exit",
        "camera_index": 0,
        "direction": "OUT",
        "location": "Main Exit",
    },
}


def get_camera(camera_id: str, direction_override: str = None, camera_name_override: str = None):
    if isinstance(camera_id, dict):
        cam = dict(camera_id)
        if direction_override:
            cam["direction"] = direction_override
        if camera_name_override:
            cam["camera_name"] = camera_name_override
        return cam

    if camera_id in CAMERAS:
        cam = dict(CAMERAS[camera_id])
        if direction_override:
            cam["direction"] = direction_override
        if camera_name_override:
            cam["camera_name"] = camera_name_override
        return cam

    c = CameraManager.get_camera(camera_id)
    if c:
        return {
            "camera_id": c["camera_id"],
            "camera_name": camera_name_override or c["camera_name"],
            "camera_index": c["url_or_index"],
            "url_or_index": c["url_or_index"],
            "camera_type": c["camera_type"],
            "direction": direction_override or c["direction"],
            "location": c["location"],
        }

    # Fallback for dynamic sources (e.g. video uploads, direct webcam indices, custom RTSP URLs)
    determined_direction = direction_override or ("OUT" if "out" in str(camera_id).lower() else "IN")
    return {
        "camera_id": str(camera_id),
        "camera_name": camera_name_override or str(camera_id),
        "camera_type": "webcam" if str(camera_id).isdigit() else "rtsp",
        "url_or_index": str(camera_id),
        "direction": determined_direction,
        "location": "Live Stream / CCTV File",
    }



def get_latest_event(camera_id: str = None, event_type: str = None):
    db = SessionLocal()
    try:
        q = db.query(AttendanceEvent).filter(AttendanceEvent.is_duplicate == 0,
                                               AttendanceEvent.is_unexpected == 0)
        if camera_id:
            q = q.filter(AttendanceEvent.camera_id == camera_id)
        if event_type:
            q = q.filter(AttendanceEvent.event_type == event_type)
        row = q.order_by(AttendanceEvent.id.desc()).first()
        if not row:
            return None
        return {
            "employee_id": row.employee_id,
            "employee_name": row.employee_name,
            "event_type": row.event_type,
            "event_time": row.event_time,
            "camera_name": row.camera_name,
        }
    finally:
        db.close()


def get_recent_events(limit: int = 20):
    db = SessionLocal()
    try:
        rows = db.query(AttendanceEvent).filter(
            AttendanceEvent.is_duplicate == 0,
            AttendanceEvent.is_unexpected == 0
        ).order_by(AttendanceEvent.id.desc()).limit(limit).all()
        return [
            {
                "employee_id": r.employee_id,
                "employee_name": r.employee_name,
                "event_type": r.event_type,
                "event_date": r.event_date,
                "event_time": r.event_time,
                "camera_name": r.camera_name,
                "camera_location": r.camera_location,
            }
            for r in rows
        ]
    finally:
        db.close()


class InOutEngine:
    """
    Consumes CONFIRMED recognitions (from RecognitionConfirmer) and decides
    whether to fire an IN or OUT event, respecting:
      - per-employee-per-direction cooldown (no repeated events every frame)
      - sequence validity (can't go IN while already Inside, etc.)
    and maintains attendance_events / attendance_intervals / attendance_daily.
    """

    def __init__(self, in_cooldown_seconds: float = None, out_cooldown_seconds: float = None):
        self.in_cooldown_seconds = in_cooldown_seconds
        self.out_cooldown_seconds = out_cooldown_seconds

        # key = (employee_id, event_type) -> last fired unix timestamp
        self._last_event_time = {}

    def get_cooldown(self, event_type: str) -> float:
        if event_type == "IN" and self.in_cooldown_seconds is not None:
            return self.in_cooldown_seconds
        if event_type == "OUT" and self.out_cooldown_seconds is not None:
            return self.out_cooldown_seconds
        return SettingsService.get_float("cooldown_duration", 45.0)

    # -----------------------------------------------------------------
    def _in_cooldown(self, employee_id: str, event_type: str, now: float) -> bool:
        key = (employee_id, event_type)
        last = self._last_event_time.get(key)
        if last is None:
            return False
        window = self.get_cooldown(event_type)
        return (now - last) < window

    def _touch_cooldown(self, employee_id: str, event_type: str, now: float):
        self._last_event_time[(employee_id, event_type)] = now

    # -----------------------------------------------------------------
    def process_confirmed_face(self, employee: dict, camera_id: str, similarity: float,
                                screenshot_path: str = None, source_type: str = "webcam",
                                session_id: str = None, direction_override: str = None,
                                camera_name_override: str = None):
        camera = get_camera(camera_id, direction_override=direction_override, camera_name_override=camera_name_override)
        if not camera:
            return {"movement_state": MovementState.WAITING, "event_created": False, "reason": "unknown_camera"}


        event_type = camera["direction"]   # "IN" or "OUT"
        if event_type not in ("IN", "OUT"):
            return {"movement_state": MovementState.WAITING, "event_created": False, "reason": "general_camera"}

        now = time.time()
        emp_id = employee["employee_id"]

        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            now_time_str = datetime.now().strftime("%H:%M:%S")

            session_row = db.query(AttendanceSession).filter(
                AttendanceSession.employee_id == emp_id,
                AttendanceSession.date == today
            ).first()

            current_status = session_row.current_status if session_row else "Outside"

            # ---- Sequence validation 
            if event_type == "IN" and current_status == "Inside":
                self._log_event(db, employee, "IN", camera, similarity, screenshot_path,
                                 source_type, session_id, today, now_time_str,
                                 is_duplicate=1, is_unexpected=0)
                db.commit()
                return {"movement_state": MovementState.IN, "event_created": False, "reason": "duplicate_state"}

            if event_type == "OUT" and current_status != "Inside":
                self._log_event(db, employee, "OUT", camera, similarity, screenshot_path,
                                 source_type, session_id, today, now_time_str,
                                 is_duplicate=0, is_unexpected=1)
                db.commit()
                return {"movement_state": MovementState.OUT, "event_created": False, "reason": "unexpected"}

            # ---- Cooldown 
            if self._in_cooldown(emp_id, event_type, now):
                self._log_event(db, employee, event_type, camera, similarity, screenshot_path,
                                 source_type, session_id, today, now_time_str,
                                 is_duplicate=1, is_unexpected=0)
                db.commit()
                return {"movement_state": event_type, "event_created": False, "reason": "cooldown"}

            # ---- Fire the event 
            self._touch_cooldown(emp_id, event_type, now)
            self._log_event(db, employee, event_type, camera, similarity, screenshot_path,
                             source_type, session_id, today, now_time_str,
                             is_duplicate=0, is_unexpected=0)

            if event_type == "IN":
                self._open_interval(db, emp_id, camera, today, now_time_str, screenshot_path)
                self._update_session(db, employee, today, event_type="IN", event_time=now_time_str)
            else:
                self._close_interval(db, emp_id, camera, today, now_time_str, screenshot_path)
                self._update_session(db, employee, today, event_type="OUT", event_time=now_time_str)

            # Sync legacy Attendance table for universal backward compatibility
            self._sync_legacy_attendance(db, employee, camera, today, screenshot_path)

            db.commit()
            return {"movement_state": event_type, "event_created": True, "reason": "created"}

        except Exception as e:
            db.rollback()
            print(f"[InOutEngine] Error: {e}")
            return {"movement_state": MovementState.WAITING, "event_created": False, "reason": "error"}
        finally:
            db.close()


    def _sync_legacy_attendance(self, db, employee, camera, today, screenshot_path):
        try:
            now_secs = float(time.time() % 86400)
            existing = db.query(Attendance).filter(
                Attendance.employee_id == employee["employee_id"],
                Attendance.date == today
            ).first()

            if existing:
                existing.last_seen = now_secs
                existing.total_frames = (existing.total_frames or 0) + 1
                if screenshot_path and not existing.screenshot:
                    existing.screenshot = screenshot_path
            else:
                db.add(Attendance(
                    employee_id=employee["employee_id"],
                    employee_name=employee["name"],
                    date=today,
                    camera_name=camera.get("camera_name", "Camera"),
                    first_seen=now_secs,
                    last_seen=now_secs,
                    total_frames=1,
                    status="Present",
                    screenshot=screenshot_path
                ))
            db.flush()
        except Exception as e:
            print(f"[InOutEngine] Error syncing legacy attendance: {e}")

    def _log_event(self, db, employee, event_type, camera, similarity, screenshot_path,
                    source_type, session_id, today, now_time_str, is_duplicate, is_unexpected):
        db.add(AttendanceEvent(
            employee_id=employee["employee_id"],
            employee_name=employee["name"],
            event_type=event_type,
            event_date=today,
            event_time=now_time_str,
            camera_id=camera["camera_id"],
            camera_name=camera["camera_name"],
            camera_location=camera.get("location"),
            similarity_score=round(float(similarity), 4),
            screenshot=screenshot_path,
            source_type=source_type,
            session_id=session_id,
            is_duplicate=is_duplicate,
            is_unexpected=is_unexpected,
        ))

    def _open_interval(self, db, employee_id, camera, today, now_time_str, screenshot_path):
        db.add(AttendanceInterval(
            employee_id=employee_id,
            date=today,
            in_time=now_time_str,
            out_time=None,
            duration_seconds=0.0,
            in_camera_id=camera["camera_id"],
            in_proof=screenshot_path,
        ))

    def _close_interval(self, db, employee_id, camera, today, now_time_str, screenshot_path):
        open_interval = db.query(AttendanceInterval).filter(
            AttendanceInterval.employee_id == employee_id,
            AttendanceInterval.date == today,
            AttendanceInterval.out_time.is_(None)
        ).order_by(AttendanceInterval.id.desc()).first()

        if not open_interval:
            db.add(AttendanceInterval(
                employee_id=employee_id,
                date=today,
                in_time=None,
                out_time=now_time_str,
                duration_seconds=0.0,
                out_camera_id=camera["camera_id"],
                out_proof=screenshot_path,
            ))
            return

        open_interval.out_time = now_time_str
        open_interval.out_camera_id = camera["camera_id"]
        open_interval.out_proof = screenshot_path

        if open_interval.in_time:
            in_dt = datetime.strptime(f"{open_interval.date} {open_interval.in_time}", "%Y-%m-%d %H:%M:%S")
            out_dt = datetime.strptime(f"{open_interval.date} {now_time_str}", "%Y-%m-%d %H:%M:%S")
            open_interval.duration_seconds = max(0.0, (out_dt - in_dt).total_seconds())

        db.flush()


    def _update_session(self, db, employee, today, event_type, event_time):
        session_row = db.query(AttendanceSession).filter(
            AttendanceSession.employee_id == employee["employee_id"],
            AttendanceSession.date == today
        ).first()

        if not session_row:
            session_row = AttendanceSession(
                employee_id=employee["employee_id"],
                employee_name=employee["name"],
                date=today,
                first_in=None,
                last_out=None,
                total_in_events=0,
                total_out_events=0,
                total_working_seconds=0.0,
                current_status="Outside",
            )
            db.add(session_row)
            db.flush()

        if event_type == "IN":
            if not session_row.first_in:
                session_row.first_in = event_time
            session_row.total_in_events += 1
            session_row.current_status = "Inside"
        else:
            session_row.last_out = event_time
            session_row.total_out_events += 1
            session_row.current_status = "Completed" if session_row.total_in_events > 0 else "Outside"

            intervals = db.query(AttendanceInterval).filter(
                AttendanceInterval.employee_id == employee["employee_id"],
                AttendanceInterval.date == today,
                AttendanceInterval.out_time.isnot(None)
            ).all()
            session_row.total_working_seconds = sum(i.duration_seconds or 0.0 for i in intervals)


    def get_currently_inside(self):
        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            rows = db.query(AttendanceSession).filter(
                AttendanceSession.date == today,
                AttendanceSession.current_status == "Inside"
            ).all()

            results = []
            now_dt = datetime.now()

            for r in rows:
                emp = db.query(Employee).filter(Employee.employee_id == r.employee_id).first()
                latest_interval = db.query(AttendanceInterval).filter(
                    AttendanceInterval.employee_id == r.employee_id,
                    AttendanceInterval.date == today,
                    AttendanceInterval.out_time.is_(None)
                ).order_by(AttendanceInterval.id.desc()).first()

                in_time_str = latest_interval.in_time if (latest_interval and latest_interval.in_time) else r.first_in
                duration_str = "0m"

                if in_time_str:
                    try:
                        in_dt = datetime.strptime(f"{today} {in_time_str}", "%Y-%m-%d %H:%M:%S")
                        elapsed_secs = max(0, int((now_dt - in_dt).total_seconds()))
                        hrs = elapsed_secs // 3600
                        mins = (elapsed_secs % 3600) // 60
                        if hrs > 0:
                            duration_str = f"{hrs}h {mins}m"
                        else:
                            duration_str = f"{mins}m"
                    except Exception:
                        pass

                camera_name = "Entrance Camera"
                if latest_interval and latest_interval.in_camera_id:
                    cam = get_camera(latest_interval.in_camera_id)
                    if cam:
                        camera_name = cam["camera_name"]

                results.append({
                    "employee_id": r.employee_id,
                    "employee_name": r.employee_name,
                    "department": emp.department if emp and emp.department else "General",
                    "first_in": r.first_in,
                    "last_in_time": in_time_str or r.first_in,
                    "camera_name": camera_name,
                    "duration_since_in": duration_str,
                    "date": r.date,
                })
            return results
        finally:
            db.close()

