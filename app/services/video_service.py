import cv2
import os
import time
import uuid
from datetime import datetime

from app.face_engine import app as face_model
from app.recognizer import recognize
from app.database import SessionLocal
from app.models import VideoSession, UnknownFace
from app.services.embedding_service import load_embeddings
from app.services.attendance_service import AttendanceManager

# In-memory dictionary for active progress tracking
PROCESSING_STATUS = {}

def get_processing_status(session_id: str):
    return PROCESSING_STATUS.get(session_id, {"status": "not_found"})

def analyze_video(video_path: str, camera_name: str, attendance_date: str, session_id: str = None):
    if not session_id:
        session_id = str(uuid.uuid4())

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        PROCESSING_STATUS[session_id] = {
            "status": "failed",
            "message": "Cannot open video file."
        }
        return {
            "status": False,
            "message": "Cannot open video file."
        }

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_filename = os.path.basename(video_path)

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "progress": 0,
        "current_frame": 0,
        "total_frames": total_frames,
        "recognized_faces": 0,
        "unknown_faces": 0,
        "start_time": time.time()
    }

    attendance_mgr = AttendanceManager()
    employees = load_embeddings()

    screenshot_folder = "static/screenshots"
    unknown_folder = "static/uploads/unknown_faces"
    os.makedirs(screenshot_folder, exist_ok=True)
    os.makedirs(unknown_folder, exist_ok=True)

    start_time = time.time()
    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0

    db = SessionLocal()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1

            # Process 1 out of every 3 frames for high speed & performance
            if frame_number % 3 != 0:
                continue

            processed_count += 1
            faces = face_model.get(frame)

            for face in faces:
                employee, score = recognize(face.embedding, employees)

                if employee:
                    recognized_count += 1
                    filename = f"{employee['employee_id']}_{frame_number}.jpg"
                    screenshot_path = os.path.join(screenshot_folder, filename)
                    
                    # Draw bounding box and label on screenshot
                    annotated_frame = frame.copy()
                    bbox = [int(b) for b in face.bbox]
                    cv2.rectangle(annotated_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                    cv2.putText(annotated_frame, f"{employee['name']} ({score:.2f})", 
                                (bbox[0], max(0, bbox[1] - 10)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    cv2.imwrite(screenshot_path, annotated_frame)
                    attendance_mgr.mark(employee, frame_number, fps, filename)
                else:
                    unknown_count += 1
                    # Save unknown face crop
                    bbox = [int(b) for b in face.bbox]
                    h_img, w_img, _ = frame.shape
                    x1, y1 = max(0, bbox[0]-10), max(0, bbox[1]-10)
                    x2, y2 = min(w_img, bbox[2]+10), min(h_img, bbox[3]+10)
                    face_crop = frame[y1:y2, x1:x2]
                    
                    unk_filename = f"unk_{session_id[:8]}_{frame_number}_{unknown_count}.jpg"
                    unk_path = os.path.join(unknown_folder, unk_filename)
                    if face_crop.size > 0:
                        cv2.imwrite(unk_path, face_crop)
                        
                        # Add to UnknownFace DB table
                        timestamp_str = f"{round(frame_number / fps, 2)}s"
                        db_unk = UnknownFace(
                            timestamp=timestamp_str,
                            frame_number=frame_number,
                            confidence=round(float(score) if 'score' in locals() else 0.0, 2),
                            image_path=unk_filename,
                            status="New"
                        )
                        db.add(db_unk)

            # Update status
            progress_pct = int((frame_number / total_frames) * 100) if total_frames > 0 else 100
            PROCESSING_STATUS[session_id].update({
                "progress": progress_pct,
                "current_frame": frame_number,
                "recognized_faces": recognized_count,
                "unknown_faces": unknown_count
            })

    except Exception as e:
        print(f"[VideoService] Error during processing: {e}")
    finally:
        cap.release()

    processing_time = round(time.time() - start_time, 2)

    # Save attendance records
    attendance_mgr.save(camera_name, attendance_date)

    # Create VideoSession database record
    video_session = VideoSession(
        video_name=video_filename,
        camera_name=camera_name,
        attendance_date=attendance_date,
        total_frames=total_frames,
        processed_frames=processed_count,
        recognized_faces=recognized_count,
        unknown_faces=unknown_count,
        processing_time=processing_time,
        fps=round(fps, 2),
        status="Completed"
    )
    db.add(video_session)
    db.commit()
    db.close()

    result = {
        "status": True,
        "session_id": session_id,
        "video_name": video_filename,
        "camera_name": camera_name,
        "attendance_date": attendance_date,
        "total_frames": total_frames,
        "processed_frames": processed_count,
        "recognized_faces": recognized_count,
        "unknown_faces": unknown_count,
        "records_marked": len(attendance_mgr.get_records()),
        "fps": round(fps, 2),
        "resolution": f"{width}x{height}",
        "processing_time": processing_time
    }

    PROCESSING_STATUS[session_id] = {
        "status": "completed",
        "progress": 100,
        "result": result
    }

    return result