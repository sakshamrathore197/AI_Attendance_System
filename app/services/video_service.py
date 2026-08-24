import cv2
import os
import time
import uuid
from datetime import datetime

from app.face_engine import app as face_model
from app.recognizer import recognize, cosine_similarity
from app.database import SessionLocal
from app.models import VideoSession, UnknownFace
from app.services.embedding_service import load_embeddings
from app.services.attendance_service import AttendanceManager
from app.services.recognition_confirmer import RecognitionConfirmer, RecognitionState
from app.services.inout_engine import InOutEngine, get_camera
from app.services.settings_service import SettingsService
from app.services.camera_manager import CameraManager

# Shared across all live sessions so match streaks and IN/OUT
# cooldowns persist for as long as the app is running.
_CONFIRMER = RecognitionConfirmer()
_INOUT_ENGINE = InOutEngine()

# Session unknown tracks for embedding-based unknown face deduplication & quality updates
_SESSION_UNKNOWN_TRACKS = {}

STATE_COLORS = {
    RecognitionState.RECOGNIZED: (0, 255, 0),        # green
    RecognitionState.CONFIRMING: (0, 200, 255),      # amber
    RecognitionState.LOW_CONFIDENCE: (0, 140, 255),  # orange
    RecognitionState.UNKNOWN: (0, 0, 255),           # red
}

# In-memory dictionary for active progress tracking
PROCESSING_STATUS = {}

# Lets a live session be stopped from another request
STREAM_CONTROL = {}

# Active cv2.VideoCapture objects by session_id for immediate hardware release
ACTIVE_CAPTURES = {}

OUTPUT_VIDEO_FOLDER = "static/processed_videos"
SCREENSHOT_FOLDER = "static/screenshots"
UNKNOWN_FOLDER = "static/uploads/unknown_faces"


def get_processing_status(session_id: str):
    return PROCESSING_STATUS.get(session_id, {"status": "not_found"})


def request_stream_stop(session_id: str):
    """Signal a running live stream to stop immediately and release hardware capture."""
    STREAM_CONTROL[session_id] = {"stop": True}
    
    # Immediately release capture if active in memory to turn off webcam LED / free RTSP stream
    cap = ACTIVE_CAPTURES.pop(session_id, None)
    if cap is not None:
        try:
            cap.release()
        except Exception as e:
            print(f"[VideoService] Error releasing active capture for {session_id}: {e}")


def _ensure_folders():
    os.makedirs(OUTPUT_VIDEO_FOLDER, exist_ok=True)
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    os.makedirs(UNKNOWN_FOLDER, exist_ok=True)


def _make_writer(session_id: str, width: int, height: int, fps: float):
    _ensure_folders()
    output_path = os.path.join(OUTPUT_VIDEO_FOLDER, f"{session_id}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps if fps > 0 else 25.0, (width, height))
    return writer, output_path


def _process_unknown_face_dedup(face, frame, frame_number, fps, camera_id, session_id, db, unknown_count_ref, save_unknowns=True):
    """
    Deduplicates unknown face records using face embedding similarity:
    1. Only ONE database record is created per unique unknown person per session.
    2. The same unknown person is NEVER saved again as a duplicate row in another frame.
    3. Overwrites the saved screenshot crop if a higher quality/clearer frame of the person is detected.
    """
    if not save_unknowns:
        return False

    now_str = datetime.now().strftime("%H:%M:%S")
    emb = face.embedding
    quality_score = float(getattr(face, "det_score", 0.90))

    bbox = [int(b) for b in face.bbox]
    crop_w = max(1, bbox[2] - bbox[0])
    crop_h = max(1, bbox[3] - bbox[1])
    area_quality = crop_w * crop_h
    current_quality = quality_score * (1.0 + min(1.0, area_quality / 40000.0))

    session_tracks = _SESSION_UNKNOWN_TRACKS.get(session_id, [])

    best_match = None
    best_sim = -1.0

    for track in session_tracks:
        sim = cosine_similarity(emb, track["embedding"])
        if sim > best_sim:
            best_sim = sim
            best_match = track

    # Cosine similarity threshold for matching the same unknown person (0.45)
    if best_match and best_sim >= 0.45:
        rec = db.query(UnknownFace).filter(UnknownFace.id == best_match["record_id"]).first()
        if rec:
            rec.last_seen = now_str
            rec.seen_count += 1

            # If current frame has a higher quality screenshot, overwrite the file
            if current_quality > best_match["best_quality"]:
                h_img, w_img, _ = frame.shape
                x1, y1 = max(0, bbox[0] - 10), max(0, bbox[1] - 10)
                x2, y2 = min(w_img, bbox[2] + 10), min(h_img, bbox[3] + 10)
                face_crop = frame[y1:y2, x1:x2]

                if face_crop.size > 0:
                    unk_path = os.path.join(UNKNOWN_FOLDER, rec.image_path)
                    cv2.imwrite(unk_path, face_crop)
                    rec.confidence = round(float(quality_score), 2)
                    best_match["best_quality"] = current_quality
                    best_match["embedding"] = (best_match["embedding"] * 0.5) + (emb * 0.5)
        return False
    else:
        # New unknown person detected: create 1 new record
        h_img, w_img, _ = frame.shape
        x1, y1 = max(0, bbox[0] - 10), max(0, bbox[1] - 10)
        x2, y2 = min(w_img, bbox[2] + 10), min(h_img, bbox[3] + 10)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size > 0:
            unknown_count_ref[0] += 1
            unk_filename = f"unk_{camera_id}_{session_id[:8]}_{frame_number}_{unknown_count_ref[0]}.jpg"
            unk_path = os.path.join(UNKNOWN_FOLDER, unk_filename)
            cv2.imwrite(unk_path, face_crop)

            timestamp_str = f"{round(frame_number / fps, 2)}s" if fps > 0 else now_str

            new_rec = UnknownFace(
                timestamp=timestamp_str,
                frame_number=frame_number,
                confidence=round(float(quality_score), 2),
                image_path=unk_filename,
                camera_id=camera_id,
                camera_name=camera_id,
                first_seen=now_str,
                last_seen=now_str,
                seen_count=1,
                status="New"
            )
            db.add(new_rec)
            db.flush()

            session_tracks.append({
                "record_id": new_rec.id,
                "embedding": emb,
                "best_quality": current_quality,
            })
            _SESSION_UNKNOWN_TRACKS[session_id] = session_tracks
        return True


def _process_frame_inout_unified(frame, frame_number, camera_id, camera_name, direction,
                                 employees, session_id, db, unknown_count_ref, stats_ref,
                                 source_type="webcam", force_confirm=False):
    """
    Unified frame processor for ALL sources (Webcam, RTSP, and Uploaded Video).
    Runs face detection, recognition, multi-frame confirmation, cooldown-based
    IN/OUT event logging, interval tracking, and daily summary persistence.
    """
    annotated_frame = frame.copy()
    faces = face_model.get(frame)

    recognized_delta = 0
    unknown_delta = 0

    save_screenshots = SettingsService.get_bool("screenshot_saving", True)
    save_unknowns = SettingsService.get_bool("unknown_face_saving", True)

    for face in faces:
        employee, score = recognize(face.embedding, employees)
        bbox = [int(b) for b in face.bbox]

        if employee:
            recognized_delta += 1
            stats_ref["employees_recognized"].add(employee["employee_id"])

            conf = _CONFIRMER.observe(camera_id, employee["employee_id"], score)
            color = STATE_COLORS.get(conf["state"], (0, 255, 0))

            movement_label = "Waiting"
            is_confirmed = conf["confirmed"] or force_confirm

            if is_confirmed:
                screenshot_filename = None
                if save_screenshots:
                    screenshot_filename = f"{employee['employee_id']}_{camera_id}_{frame_number}.jpg"
                    screenshot_path = os.path.join(SCREENSHOT_FOLDER, screenshot_filename)
                    cv2.imwrite(screenshot_path, annotated_frame)

                outcome = _INOUT_ENGINE.process_confirmed_face(
                    employee=employee,
                    camera_id=camera_id,
                    similarity=score,
                    screenshot_path=screenshot_filename,
                    source_type=source_type,
                    session_id=session_id,
                    direction_override=direction,
                    camera_name_override=camera_name
                )
                movement_label = outcome["movement_state"]
                if outcome["event_created"]:
                    stats_ref[f"latest_{outcome['movement_state'].lower()}_event"] = {
                        "employee_name": employee["name"],
                        "event_type": outcome["movement_state"],
                        "time": datetime.now().strftime("%H:%M:%S"),
                    }

            cv2.rectangle(annotated_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            line1 = f"{employee['name']} ({employee['employee_id']})"
            line2 = f"{conf['state']} | sim {score:.2f} | {movement_label}"
            cv2.putText(annotated_frame, line1, (bbox[0], max(0, bbox[1] - 28)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            cv2.putText(annotated_frame, line2, (bbox[0], max(0, bbox[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        else:
            unknown_delta += 1
            color = STATE_COLORS[RecognitionState.UNKNOWN]
            cv2.rectangle(annotated_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            cv2.putText(annotated_frame, f"Unknown ({score:.2f})", (bbox[0], max(0, bbox[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            _process_unknown_face_dedup(
                face, frame, frame_number, 25.0, camera_id, session_id, db, unknown_count_ref, save_unknowns
            )

    return annotated_frame, recognized_delta, unknown_delta


# ---------------------------------------------------------------------------
# Option 1: Live CCTV RTSP Stream Generator (with Auto-Reconnect)
# ---------------------------------------------------------------------------
def stream_rtsp_live(rtsp_url: str, camera_name: str, direction: str, attendance_date: str, session_id: str):
    """
    Real-time RTSP stream processing with automatic reconnection loop on disconnect.
    """
    STREAM_CONTROL[session_id] = {"stop": False}
    camera_id = f"rtsp_{session_id[:8]}"

    _ensure_folders()
    employees = load_embeddings()
    db = SessionLocal()

    stats_ref = {
        "employees_recognized": set(),
        "latest_in_event": None,
        "latest_out_event": None,
    }

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "connection_status": "Connecting",
        "camera_id": camera_id,
        "camera_name": camera_name,
        "direction": direction,
        "resolution": "—",
        "current_fps": 0,
        "faces_detected": 0,
        "employees_recognized": 0,
        "unknown_faces": 0,
        "reconnect_attempts": 0,
        "latest_in_event": None,
        "latest_out_event": None,
        "start_time": time.time()
    }

    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0
    unknown_count_ref = [0]
    writer = None
    output_video_path = None
    start_time = time.time()
    reconnect_attempts = 0
    max_reconnect_attempts = 15

    try:
        while True:
            if STREAM_CONTROL.get(session_id, {}).get("stop"):
                break

            cap = cv2.VideoCapture(rtsp_url)
            ACTIVE_CAPTURES[session_id] = cap

            if not cap.isOpened():
                reconnect_attempts += 1
                PROCESSING_STATUS[session_id].update({
                    "connection_status": f"Reconnecting ({reconnect_attempts}/{max_reconnect_attempts})",
                    "reconnect_attempts": reconnect_attempts
                })
                if reconnect_attempts >= max_reconnect_attempts:
                    PROCESSING_STATUS[session_id]["connection_status"] = "Error"
                    break
                time.sleep(2.0)
                continue

            # Connected successfully!
            reconnect_attempts = 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
            source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

            if writer is None:
                writer, output_video_path = _make_writer(session_id, width, height, source_fps)

            PROCESSING_STATUS[session_id].update({
                "connection_status": "Connected",
                "resolution": f"{width}x{height}",
            })

            fps_window_start = time.time()
            fps_window_frames = 0
            current_fps = 0

            while True:
                if STREAM_CONTROL.get(session_id, {}).get("stop"):
                    break

                ret, frame = cap.read()
                if not ret or frame is None:
                    # Stream drop detected: break inner loop to trigger auto-reconnect
                    PROCESSING_STATUS[session_id]["connection_status"] = "Stream Interrupted - Reconnecting"
                    break

                frame_number += 1
                processed_count += 1

                annotated_frame, rec_delta, unk_delta = _process_frame_inout_unified(
                    frame=frame,
                    frame_number=frame_number,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    direction=direction,
                    employees=employees,
                    session_id=session_id,
                    db=db,
                    unknown_count_ref=unknown_count_ref,
                    stats_ref=stats_ref,
                    source_type="rtsp"
                )
                recognized_count += rec_delta
                unknown_count += unk_delta

                if writer is not None:
                    writer.write(annotated_frame)

                fps_window_frames += 1
                elapsed = time.time() - fps_window_start
                if elapsed >= 1.0:
                    current_fps = round(fps_window_frames / elapsed, 1)
                    fps_window_frames = 0
                    fps_window_start = time.time()

                PROCESSING_STATUS[session_id].update({
                    "current_frame": frame_number,
                    "current_fps": current_fps,
                    "faces_detected": rec_delta + unk_delta,
                    "employees_recognized": len(stats_ref["employees_recognized"]),
                    "unknown_faces": unknown_count,
                    "latest_in_event": stats_ref["latest_in_event"],
                    "latest_out_event": stats_ref["latest_out_event"],
                })

                db.commit()

                ok, buffer = cv2.imencode(".jpg", annotated_frame)
                if not ok:
                    continue

                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

            cap.release()
            ACTIVE_CAPTURES.pop(session_id, None)

    except GeneratorExit:
        pass
    except Exception as e:
        print(f"[VideoService] RTSP Stream Exception: {e}")
        PROCESSING_STATUS[session_id]["connection_status"] = "Error"
    finally:
        cap = ACTIVE_CAPTURES.pop(session_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        if writer is not None:
            writer.release()
        STREAM_CONTROL.pop(session_id, None)

        processing_time = round(time.time() - start_time, 2)
        rel_output_path = os.path.relpath(output_video_path, "static") if output_video_path else None
        video_session = VideoSession(
            video_name=f"rtsp_{camera_name}",
            camera_name=camera_name,
            attendance_date=attendance_date or datetime.now().strftime("%Y-%m-%d"),
            total_frames=frame_number,
            processed_frames=processed_count,
            recognized_faces=recognized_count,
            unknown_faces=unknown_count,
            processing_time=processing_time,
            fps=25.0,
            status="Completed",
            output_video_path=rel_output_path,
            source_type="rtsp",
        )
        db.add(video_session)
        db.commit()

        PROCESSING_STATUS[session_id].update({
            "status": "completed",
            "connection_status": "Disconnected",
            "current_fps": 0,
            "result": {
                "recognized_faces": recognized_count,
                "unknown_faces": unknown_count,
                "processed_frames": processed_count,
                "processing_time": processing_time,
                "output_video_url": f"/static/{rel_output_path}" if rel_output_path else None,
            }
        })
        db.close()


# ---------------------------------------------------------------------------
# Option 2: Uploaded Video Stream Generator (Real-time Live Preview)
# ---------------------------------------------------------------------------
def stream_uploaded_video(video_path: str, camera_name: str, direction: str, attendance_date: str, session_id: str):
    """
    Streams an uploaded video frame-by-frame with real-time bounding boxes and IN/OUT persistence.
    """
    STREAM_CONTROL[session_id] = {"stop": False}
    camera_id = f"upload_{direction.lower()}_{session_id[:8]}"

    cap = cv2.VideoCapture(video_path)
    ACTIVE_CAPTURES[session_id] = cap

    if not cap.isOpened():
        PROCESSING_STATUS[session_id] = {"status": "failed", "message": "Cannot open video file."}
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    _ensure_folders()
    writer, output_video_path = _make_writer(session_id, width, height, fps)

    stats_ref = {
        "employees_recognized": set(),
        "latest_in_event": None,
        "latest_out_event": None,
    }

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "connection_status": "Connected",
        "camera_id": camera_id,
        "camera_name": camera_name,
        "direction": direction,
        "total_frames": total_frames,
        "current_frame": 0,
        "progress": 0,
        "current_fps": fps,
        "faces_detected": 0,
        "employees_recognized": 0,
        "unknown_faces": 0,
        "latest_in_event": None,
        "latest_out_event": None,
        "start_time": time.time()
    }

    employees = load_embeddings()
    db = SessionLocal()

    start_time = time.time()
    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0
    unknown_count_ref = [0]

    try:
        while True:
            if STREAM_CONTROL.get(session_id, {}).get("stop"):
                break

            ret, frame = cap.read()
            if not ret or frame is None:
                break  # End of uploaded video file

            frame_number += 1

            # Process every 2nd or 3rd frame for speed while keeping smooth video
            if frame_number % 2 == 0:
                processed_count += 1
                annotated_frame, rec_delta, unk_delta = _process_frame_inout_unified(
                    frame=frame,
                    frame_number=frame_number,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    direction=direction,
                    employees=employees,
                    session_id=session_id,
                    db=db,
                    unknown_count_ref=unknown_count_ref,
                    stats_ref=stats_ref,
                    source_type="upload",
                    force_confirm=True
                )
                recognized_count += rec_delta
                unknown_count += unk_delta
            else:
                annotated_frame = frame

            writer.write(annotated_frame)

            progress_pct = int((frame_number / total_frames) * 100) if total_frames > 0 else 100
            PROCESSING_STATUS[session_id].update({
                "progress": progress_pct,
                "current_frame": frame_number,
                "current_fps": fps,
                "faces_detected": rec_delta if frame_number % 2 == 0 else 0,
                "employees_recognized": len(stats_ref["employees_recognized"]),
                "unknown_faces": unknown_count,
                "latest_in_event": stats_ref["latest_in_event"],
                "latest_out_event": stats_ref["latest_out_event"],
            })

            db.commit()

            ok, buffer = cv2.imencode(".jpg", annotated_frame)
            if not ok:
                continue

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

    except GeneratorExit:
        pass
    except Exception as e:
        print(f"[VideoService] Error streaming uploaded video: {e}")
    finally:
        cap = ACTIVE_CAPTURES.pop(session_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        writer.release()
        STREAM_CONTROL.pop(session_id, None)

        processing_time = round(time.time() - start_time, 2)
        rel_output_path = os.path.relpath(output_video_path, "static") if output_video_path else None
        video_session = VideoSession(
            video_name=os.path.basename(video_path),
            camera_name=camera_name,
            attendance_date=attendance_date or datetime.now().strftime("%Y-%m-%d"),
            total_frames=total_frames or frame_number,
            processed_frames=processed_count,
            recognized_faces=recognized_count,
            unknown_faces=unknown_count,
            processing_time=processing_time,
            fps=round(fps, 2),
            status="Completed",
            output_video_path=rel_output_path,
            source_type="upload",
        )
        db.add(video_session)
        db.commit()

        PROCESSING_STATUS[session_id].update({
            "status": "completed",
            "progress": 100,
            "connection_status": "Disconnected",
            "result": {
                "recognized_faces": recognized_count,
                "unknown_faces": unknown_count,
                "processed_frames": processed_count,
                "processing_time": processing_time,
                "output_video_url": f"/static/{rel_output_path}" if rel_output_path else None,
            }
        })
        db.close()


# ---------------------------------------------------------------------------
# Option 3: Local Webcam Stream Generator (Testing IN & OUT)
# ---------------------------------------------------------------------------
def stream_webcam(camera_index: int, camera_name: str, direction: str, attendance_date: str, session_id: str):
    """
    Live Webcam testing stream with full IN and OUT direction support,
    instant stop and immediate hardware release.
    """
    STREAM_CONTROL[session_id] = {"stop": False}
    camera_id = f"webcam_{camera_index}_{direction.lower()}"

    try:
        cam_idx = int(camera_index)
    except ValueError:
        cam_idx = 0

    cap = cv2.VideoCapture(cam_idx)
    ACTIVE_CAPTURES[session_id] = cap

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        ACTIVE_CAPTURES.pop(session_id, None)
        PROCESSING_STATUS[session_id] = {"status": "failed", "message": f"Cannot open webcam index {camera_index}."}
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

    _ensure_folders()
    writer, output_video_path = _make_writer(session_id, width, height, source_fps)

    stats_ref = {
        "employees_recognized": set(),
        "latest_in_event": None,
        "latest_out_event": None,
    }

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "connection_status": "Connected",
        "camera_id": camera_id,
        "camera_name": camera_name,
        "direction": direction,
        "resolution": f"{width}x{height}",
        "current_fps": 0,
        "faces_detected": 0,
        "employees_recognized": 0,
        "unknown_faces": 0,
        "latest_in_event": None,
        "latest_out_event": None,
        "start_time": time.time()
    }

    employees = load_embeddings()
    db = SessionLocal()

    start_time = time.time()
    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0
    unknown_count_ref = [0]

    fps_window_start = time.time()
    fps_window_frames = 0
    current_fps = 0

    frame_interval = SettingsService.get_int("frame_processing_interval", 1)

    try:
        while True:
            if STREAM_CONTROL.get(session_id, {}).get("stop"):
                break

            ret, frame = cap.read()
            if not ret or frame is None:
                PROCESSING_STATUS[session_id]["connection_status"] = "Error"
                break

            frame_number += 1

            if frame_interval <= 1 or (frame_number % frame_interval == 0):
                processed_count += 1
                annotated_frame, rec_delta, unk_delta = _process_frame_inout_unified(
                    frame=frame,
                    frame_number=frame_number,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    direction=direction,
                    employees=employees,
                    session_id=session_id,
                    db=db,
                    unknown_count_ref=unknown_count_ref,
                    stats_ref=stats_ref,
                    source_type="webcam"
                )
                recognized_count += rec_delta
                unknown_count += unk_delta
            else:
                annotated_frame = frame

            writer.write(annotated_frame)

            fps_window_frames += 1
            elapsed = time.time() - fps_window_start
            if elapsed >= 1.0:
                current_fps = round(fps_window_frames / elapsed, 1)
                fps_window_frames = 0
                fps_window_start = time.time()

            PROCESSING_STATUS[session_id].update({
                "current_frame": frame_number,
                "current_fps": current_fps,
                "faces_detected": rec_delta + unk_delta if frame_interval <= 1 or (frame_number % frame_interval == 0) else 0,
                "employees_recognized": len(stats_ref["employees_recognized"]),
                "unknown_faces": unknown_count,
                "latest_in_event": stats_ref["latest_in_event"],
                "latest_out_event": stats_ref["latest_out_event"],
            })

            db.commit()

            ok, buffer = cv2.imencode(".jpg", annotated_frame)
            if not ok:
                continue

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

    except GeneratorExit:
        pass
    except Exception as e:
        print(f"[VideoService] Webcam exception: {e}")
    finally:
        cap = ACTIVE_CAPTURES.pop(session_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        writer.release()
        STREAM_CONTROL.pop(session_id, None)

        processing_time = round(time.time() - start_time, 2)
        rel_output_path = os.path.relpath(output_video_path, "static") if output_video_path else None
        video_session = VideoSession(
            video_name=f"webcam_{camera_index}_{direction.lower()}",
            camera_name=camera_name,
            attendance_date=attendance_date or datetime.now().strftime("%Y-%m-%d"),
            total_frames=frame_number,
            processed_frames=processed_count,
            recognized_faces=recognized_count,
            unknown_faces=unknown_count,
            processing_time=processing_time,
            fps=round(source_fps, 2),
            status="Completed",
            output_video_path=rel_output_path,
            source_type="webcam",
        )
        db.add(video_session)
        db.commit()

        PROCESSING_STATUS[session_id].update({
            "status": "completed",
            "connection_status": "Disconnected",
            "current_fps": 0,
            "result": {
                "recognized_faces": recognized_count,
                "unknown_faces": unknown_count,
                "processed_frames": processed_count,
                "processing_time": processing_time,
                "output_video_url": f"/static/{rel_output_path}" if rel_output_path else None,
            }
        })
        db.close()


# ---------------------------------------------------------------------------
# Background Video Analysis Job (for Fast Upload Mode)
# ---------------------------------------------------------------------------
def analyze_video(video_path: str, camera_name: str, attendance_date: str, session_id: str = None, direction: str = "IN"):
    if not session_id:
        session_id = str(uuid.uuid4())

    cap = cv2.VideoCapture(video_path)
    ACTIVE_CAPTURES[session_id] = cap

    if not cap.isOpened():
        PROCESSING_STATUS[session_id] = {
            "status": "failed",
            "message": "Cannot open video file."
        }
        return {"status": False, "message": "Cannot open video file."}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_filename = os.path.basename(video_path)
    camera_id = f"bg_upload_{session_id[:8]}"

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "progress": 0,
        "current_frame": 0,
        "total_frames": total_frames,
        "recognized_faces": 0,
        "unknown_faces": 0,
        "start_time": time.time()
    }

    stats_ref = {
        "employees_recognized": set(),
        "latest_in_event": None,
        "latest_out_event": None,
    }

    employees = load_embeddings()
    _ensure_folders()
    writer, output_video_path = _make_writer(session_id, width, height, fps)

    start_time = time.time()
    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0
    unknown_count_ref = [0]

    db = SessionLocal()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_number += 1

            if frame_number % 3 != 0:
                writer.write(frame)
                continue

            processed_count += 1
            annotated_frame, rec_delta, unk_delta = _process_frame_inout_unified(
                frame=frame,
                frame_number=frame_number,
                camera_id=camera_id,
                camera_name=camera_name,
                direction=direction,
                employees=employees,
                session_id=session_id,
                db=db,
                unknown_count_ref=unknown_count_ref,
                stats_ref=stats_ref,
                source_type="upload",
                force_confirm=True
            )
            recognized_count += rec_delta
            unknown_count += unk_delta

            writer.write(annotated_frame)

            progress_pct = int((frame_number / total_frames) * 100) if total_frames > 0 else 100
            PROCESSING_STATUS[session_id].update({
                "progress": progress_pct,
                "current_frame": frame_number,
                "recognized_faces": len(stats_ref["employees_recognized"]),
                "unknown_faces": unknown_count
            })

            db.commit()

    except Exception as e:
        print(f"[VideoService] Error during background processing: {e}")
    finally:
        cap = ACTIVE_CAPTURES.pop(session_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        writer.release()

        processing_time = round(time.time() - start_time, 2)
        rel_output_path = os.path.relpath(output_video_path, "static") if output_video_path else None
        video_session = VideoSession(
            video_name=video_filename,
            camera_name=camera_name,
            attendance_date=attendance_date or datetime.now().strftime("%Y-%m-%d"),
            total_frames=total_frames,
            processed_frames=processed_count,
            recognized_faces=len(stats_ref["employees_recognized"]),
            unknown_faces=unknown_count,
            processing_time=processing_time,
            fps=round(fps, 2) if fps else 0,
            status="Completed",
            output_video_path=rel_output_path,
            source_type="upload",
        )
        db.add(video_session)
        db.commit()

        result = {
            "status": True,
            "session_id": session_id,
            "video_name": video_filename,
            "camera_name": camera_name,
            "attendance_date": attendance_date,
            "total_frames": total_frames,
            "processed_frames": processed_count,
            "recognized_faces": len(stats_ref["employees_recognized"]),
            "unknown_faces": unknown_count,
            "records_marked": len(stats_ref["employees_recognized"]),
            "fps": round(fps, 2) if fps else 0,
            "resolution": f"{width}x{height}",
            "processing_time": processing_time,
            "output_video_url": f"/static/{rel_output_path}" if rel_output_path else None,
        }

        PROCESSING_STATUS[session_id] = {
            "status": "completed",
            "progress": 100,
            "result": result
        }

        db.close()
        return result


# ---------------------------------------------------------------------------
# Compatibility wrapper for camera manager endpoints
# ---------------------------------------------------------------------------
def stream_webcam_inout(camera_id: str, session_id: str):
    cam = get_camera(camera_id)
    if not cam:
        PROCESSING_STATUS[session_id] = {"status": "failed", "message": f"Unknown camera_id '{camera_id}'."}
        return

    cam_type = cam.get("camera_type", "webcam").lower()
    raw_source = cam.get("url_or_index") or cam.get("camera_index", 0)
    direction = cam.get("direction", "IN")
    cam_name = cam.get("camera_name", str(camera_id))

    if cam_type == "rtsp" or "rtsp://" in str(raw_source):
        yield from stream_rtsp_live(str(raw_source), cam_name, direction, datetime.now().strftime("%Y-%m-%d"), session_id)
    else:
        try:
            c_idx = int(raw_source)
        except ValueError:
            c_idx = 0
        yield from stream_webcam(c_idx, cam_name, direction, datetime.now().strftime("%Y-%m-%d"), session_id)
