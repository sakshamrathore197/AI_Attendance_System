from app.database import SessionLocal
from app.models import SystemSetting

DEFAULTS = {
    "face_recognition_threshold": "0.60",
    "confirmation_frame_count": "4",
    "cooldown_duration": "45",
    "unknown_face_saving": "true",
    "screenshot_saving": "true",
    "rtsp_reconnect_interval": "10",
    "frame_processing_interval": "1",
}


class SettingsService:
    _cache = {}

    @classmethod
    def get(cls, key: str, default: str = None) -> str:
        if key in cls._cache:
            return cls._cache[key]

        db = SessionLocal()
        try:
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting:
                cls._cache[key] = setting.value
                return setting.value
        except Exception as e:
            print(f"[SettingsService] Error reading key '{key}': {e}")
        finally:
            db.close()

        val = default if default is not None else DEFAULTS.get(key, "")
        cls._cache[key] = val
        return val

    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        try:
            return float(cls.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        try:
            return int(float(cls.get(key, str(default))))
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = True) -> bool:
        val = str(cls.get(key, "true" if default else "false")).lower().strip()
        return val in ("true", "1", "yes", "on")

    @classmethod
    def set(cls, key: str, value: str, description: str = None):
        cls._cache[key] = str(value)
        db = SessionLocal()
        try:
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting:
                setting.value = str(value)
                if description:
                    setting.description = description
            else:
                setting = SystemSetting(key=key, value=str(value), description=description)
                db.add(setting)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[SettingsService] Error saving key '{key}': {e}")
        finally:
            db.close()

    @classmethod
    def get_all(cls):
        db = SessionLocal()
        try:
            rows = db.query(SystemSetting).all()
            settings_map = {k: DEFAULTS[k] for k in DEFAULTS}
            for r in rows:
                settings_map[r.key] = r.value
            return settings_map
        finally:
            db.close()

    @classmethod
    def update_all(cls, settings_dict: dict):
        for k, v in settings_dict.items():
            if k in DEFAULTS:
                cls.set(k, str(v))
        cls.clear_cache()

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()
