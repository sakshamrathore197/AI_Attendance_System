import cv2
import time
from datetime import datetime
from app.database import SessionLocal
from app.models import Camera


class CameraManager:
    """
    Manages dynamic camera definitions, status updates, connection testing,
    and camera health monitoring for Webcams and RTSP/IP cameras.
    """

    @staticmethod
    def get_all_cameras():
        db = SessionLocal()
        try:
            cameras = db.query(Camera).filter(Camera.is_active == 1).order_by(Camera.id.asc()).all()
            return [
                {
                    "id": c.id,
                    "camera_id": c.camera_id,
                    "camera_name": c.camera_name,
                    "camera_type": c.camera_type,
                    "url_or_index": c.url_or_index,
                    "location": c.location or "General Area",
                    "direction": c.direction,
                    "status": c.status,
                    "last_connected_time": c.last_connected_time or "Never",
                    "last_error": c.last_error or "None",
                    "fps": round(c.fps or 0.0, 1),
                }
                for c in cameras
            ]
        finally:
            db.close()

    @staticmethod
    def get_camera(camera_id: str):
        db = SessionLocal()
        try:
            c = db.query(Camera).filter(Camera.camera_id == camera_id).first()
            if not c:
                return None
            return {
                "id": c.id,
                "camera_id": c.camera_id,
                "camera_name": c.camera_name,
                "camera_type": c.camera_type,
                "url_or_index": c.url_or_index,
                "location": c.location or "General Area",
                "direction": c.direction,
                "status": c.status,
                "last_connected_time": c.last_connected_time,
                "last_error": c.last_error,
                "fps": c.fps or 0.0,
            }
        finally:
            db.close()

    @staticmethod
    def create_camera(data: dict):
        db = SessionLocal()
        try:
            cam_id = data["camera_id"].strip().lower().replace(" ", "_")
            existing = db.query(Camera).filter(Camera.camera_id == cam_id).first()
            if existing:
                return {"status": False, "message": f"Camera ID '{cam_id}' already exists."}

            cam = Camera(
                camera_id=cam_id,
                camera_name=data["camera_name"].strip(),
                camera_type=data.get("camera_type", "webcam").lower(),
                url_or_index=str(data.get("url_or_index", "0")).strip(),
                location=data.get("location", "").strip() or "General Area",
                direction=data.get("direction", "IN").upper(),
                status="Disconnected",
            )
            db.add(cam)
            db.commit()
            db.refresh(cam)
            return {"status": True, "message": f"Camera '{cam.camera_name}' added successfully.", "camera": cam.camera_id}
        except Exception as e:
            db.rollback()
            return {"status": False, "message": f"Error adding camera: {e}"}
        finally:
            db.close()

    @staticmethod
    def update_camera(camera_id: str, data: dict):
        db = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
            if not cam:
                return {"status": False, "message": f"Camera '{camera_id}' not found."}

            if "camera_name" in data:
                cam.camera_name = data["camera_name"].strip()
            if "camera_type" in data:
                cam.camera_type = data["camera_type"].lower()
            if "url_or_index" in data:
                cam.url_or_index = str(data["url_or_index"]).strip()
            if "location" in data:
                cam.location = data["location"].strip()
            if "direction" in data:
                cam.direction = data["direction"].upper()

            db.commit()
            return {"status": True, "message": f"Camera '{camera_id}' updated successfully."}
        except Exception as e:
            db.rollback()
            return {"status": False, "message": f"Error updating camera: {e}"}
        finally:
            db.close()

    @staticmethod
    def delete_camera(camera_id: str):
        db = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
            if not cam:
                return {"status": False, "message": f"Camera '{camera_id}' not found."}
            db.delete(cam)
            db.commit()
            return {"status": True, "message": f"Camera '{camera_id}' deleted."}
        except Exception as e:
            db.rollback()
            return {"status": False, "message": f"Error deleting camera: {e}"}
        finally:
            db.close()

    @staticmethod
    def update_status(camera_id: str, status: str, error_msg: str = None, fps: float = None):
        db = SessionLocal()
        try:
            cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
            if cam:
                cam.status = status
                if status == "Connected":
                    cam.last_connected_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cam.last_error = "None"
                elif error_msg:
                    cam.last_error = error_msg
                if fps is not None:
                    cam.fps = float(fps)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"[CameraManager] Error updating status for '{camera_id}': {e}")
        finally:
            db.close()

    @staticmethod
    def test_connection(camera_type: str, url_or_index: str):
        """
        Attempts to connect to a camera (Webcam index or RTSP URL) and capture 1 test frame.
        Returns diagnostic results.
        """
        import os
        cap_source = url_or_index
        if camera_type.lower() == "webcam":
            try:
                cap_source = int(url_or_index)
            except ValueError:
                return {
                    "status": False,
                    "message": f"Invalid webcam index '{url_or_index}'. Must be an integer like 0, 1, 2.",
                }
        else:
            # Enable TCP transport and 5s socket timeout for RTSP/IP cameras
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"

        cap = cv2.VideoCapture(cap_source, cv2.CAP_FFMPEG if camera_type.lower() != "webcam" else cv2.CAP_ANY)
        if not cap.isOpened():
            return {
                "status": False,
                "message": f"Failed to open {camera_type.upper()} source. The camera actively closed the connection or credentials/path are incorrect.",
            }

        start = time.time()
        ret, frame = cap.read()
        latency = round((time.time() - start) * 1000, 1)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if cap.isOpened() else 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if cap.isOpened() else 0
        fps = round(cap.get(cv2.CAP_PROP_FPS) or 25.0, 1)

        cap.release()

        if not ret or frame is None:
            return {
                "status": False,
                "message": f"Opened source '{url_or_index}', but could not read video frame.",
            }

        return {
            "status": True,
            "message": f"Successfully connected to {camera_type.upper()} ({width}x{height} @ {fps} FPS, Latency: {latency}ms).",
            "resolution": f"{width}x{height}",
            "fps": fps,
            "latency_ms": latency,
        }
