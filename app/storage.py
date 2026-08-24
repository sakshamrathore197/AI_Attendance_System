from sqlalchemy import text
from app.database import Base, engine, SessionLocal
from app.models import Camera, SystemSetting

DEFAULT_SETTINGS = [
    ("face_recognition_threshold", "0.60", "Cosine similarity threshold for face recognition (0.50 - 0.80)"),
    ("confirmation_frame_count", "4", "Number of consecutive matching frames required to confirm face (3 - 5)"),
    ("cooldown_duration", "45", "Cooldown duration in seconds to prevent duplicate attendance events"),
    ("unknown_face_saving", "true", "Enable or disable saving unknown face crops"),
    ("screenshot_saving", "true", "Enable or disable saving event screenshots"),
    ("rtsp_reconnect_interval", "10", "Interval in seconds to attempt RTSP stream reconnection"),
    ("frame_processing_interval", "1", "Process every Nth frame (1 = process all frames, 2 = alternate)"),
]

DEFAULT_CAMERAS = [
    {
        "camera_id": "webcam-in",
        "camera_name": "Webcam - Entrance",
        "camera_type": "webcam",
        "url_or_index": "0",
        "location": "Main Entrance",
        "direction": "IN",
        "status": "Disconnected",
    },
    {
        "camera_id": "webcam-out",
        "camera_name": "Webcam - Exit",
        "camera_type": "webcam",
        "url_or_index": "0",
        "location": "Main Exit",
        "direction": "OUT",
        "status": "Disconnected",
    },
]


def init_db():
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        # 1. Alter unknown_faces if columns missing
        try:
            res = conn.execute(text("PRAGMA table_info(unknown_faces)"))
            cols = [r[1] for r in res.fetchall()]
            if cols:
                for col_name, col_type in [
                    ("created_at", "DATETIME"),
                    ("camera_id", "VARCHAR"),
                    ("camera_name", "VARCHAR"),
                    ("first_seen", "VARCHAR"),
                    ("last_seen", "VARCHAR"),
                    ("seen_count", "INTEGER DEFAULT 1"),
                ]:
                    if col_name not in cols:
                        conn.execute(text(f"ALTER TABLE unknown_faces ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
        except Exception as e:
            print(f"[DB Migration] UnknownFace check error: {e}")

        # 2. Unique index on attendance
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_employee_date "
                "ON attendance (employee_id, date)"
            ))
            conn.commit()
        except Exception as e:
            print(f"[DB Migration] Unique index info: {e}")

    # 3. Seed Default Settings & Cameras
    db = SessionLocal()
    try:
        for k, v, desc in DEFAULT_SETTINGS:
            existing = db.query(SystemSetting).filter(SystemSetting.key == k).first()
            if not existing:
                db.add(SystemSetting(key=k, value=v, description=desc))

        for c_data in DEFAULT_CAMERAS:
            existing = db.query(Camera).filter(Camera.camera_id == c_data["camera_id"]).first()
            if not existing:
                db.add(Camera(**c_data))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[DB Migration] Seed default data error: {e}")
    finally:
        db.close()