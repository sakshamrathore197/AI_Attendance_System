from sqlalchemy import text, inspect
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

    try:
        inspector = inspect(engine)
        if inspector.has_table("unknown_faces"):
            cols = [c["name"] for c in inspector.get_columns("unknown_faces")]
            with engine.connect() as conn:
                for col_name, col_type in [
                    ("created_at", "TIMESTAMP"),
                    ("camera_id", "VARCHAR(255)"),
                    ("camera_name", "VARCHAR(255)"),
                    ("first_seen", "VARCHAR(255)"),
                    ("last_seen", "VARCHAR(255)"),
                    ("seen_count", "INTEGER DEFAULT 1"),
                ]:
                    if col_name not in cols:
                        conn.execute(text(f"ALTER TABLE unknown_faces ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
    except Exception as e:
        print(f"[DB Migration] Schema check info: {e}")


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