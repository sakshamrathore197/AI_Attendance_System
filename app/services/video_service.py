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
from app.services.recognition_manager import RecognitionManager
from app.services.track_manager import ByteTracker

# In-memory dictionary for active progress tracking
PROCESSING_STATUS = {}

# Lets a live session (webcam or upload-stream) be stopped from another request
STREAM_CONTROL = {}

OUTPUT_VIDEO_FOLDER = "static/processed_videos"
SCREENSHOT_FOLDER = "static/screenshots"
UNKNOWN_FOLDER = "static/uploads/unknown_faces"


def get_processing_status(session_id: str):
    return PROCESSING_STATUS.get(session_id, {"status": "not_found"})


def request_stream_stop(session_id: str):
    """Signal a running live stream (webcam or live-upload) to stop after
    the current frame and finalize (save attendance, close the writer)."""
    STREAM_CONTROL[session_id] = {"stop": True}


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


def _process_frame(frame, frame_number, fps, employees, attendance_mgr,
                    tracker, recognition_mgr, session_id, db, unknown_count_ref,
                    session_unknown_faces, session_identified_employees):
    annotated_frame = frame.copy()
    faces = face_model.get(frame)

    # Update tracks using ByteTrack 2-stage association
    active_tracks = tracker.update(faces)

    recognized_delta = 0
    unknown_delta = 0

    for track in active_tracks:
        bbox = [int(b) for b in track.bbox]

        # Perform recognition on face embedding if available (using session_identified_employees for CCTV resilience)
        if track.embedding is not None:
            employee, score = recognize(track.embedding, employees, session_identified_employees)
        else:
            employee, score = None, 0.0

        # Update track confirmation state (confirm_frames=1 -> immediate lock-in)
        track = recognition_mgr.update_strack(track, employee, score)

        if track.confirmed and track.employee:
            session_identified_employees[track.employee["employee_id"]] = track.employee
            emp = track.employee
            rec_score = track.score
            color = (0, 255, 0)
            label = f"{emp['name']} ({rec_score:.2f})"

            cv2.rectangle(annotated_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            cv2.putText(annotated_frame, label, (bbox[0], max(0, bbox[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            filename = f"{emp['employee_id']}_{frame_number}.jpg"
            screenshot_path = os.path.join(SCREENSHOT_FOLDER, filename)
            cv2.imwrite(screenshot_path, annotated_frame)

            # Continuous last_seen attendance update
            attendance_mgr.mark(emp, frame_number, fps, filename)
            recognized_delta += 1

            # REQUIREMENT: "if person is identified once, should not move to unknown"
            # Purge any transient UnknownFace record created before recognition was confirmed
            if track.unknown_db_id:
                unk_rec = db.query(UnknownFace).filter(UnknownFace.id == track.unknown_db_id).first()
                if unk_rec:
                    crop_path = os.path.join(UNKNOWN_FOLDER, unk_rec.image_path)
                    if os.path.exists(crop_path):
                        try:
                            os.remove(crop_path)
                        except Exception:
                            pass
                    db.delete(unk_rec)
                    db.commit()

                # Remove from session unknown face registry
                session_unknown_faces[:] = [u for u in session_unknown_faces if u["db_id"] != track.unknown_db_id]
                track.unknown_db_id = None

        else:
            color = (0, 0, 255)
            cv2.rectangle(annotated_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            cv2.putText(annotated_frame, f"Unknown ({score:.2f})", (bbox[0], max(0, bbox[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # REQUIREMENT: "there should be only one best screenshot of unknown"
            face_w = max(1, bbox[2] - bbox[0])
            face_h = max(1, bbox[3] - bbox[1])
            quality = float(track.det_score) * (face_w * face_h)

            h_img, w_img, _ = frame.shape
            x1, y1 = max(0, bbox[0] - 10), max(0, bbox[1] - 10)
            x2, y2 = min(w_img, bbox[2] + 10), min(h_img, bbox[3] + 10)
            face_crop = frame[y1:y2, x1:x2]

            if face_crop.size > 0:
                # Check if this unknown face matches an existing unknown person in session
                matched_session_unk = None
                if not track.unknown_db_id and track.embedding is not None:
                    best_sim = -1.0
                    for unk_item in session_unknown_faces:
                        sim = cosine_similarity(track.embedding, unk_item["embedding"])
                        if sim > best_sim and sim >= 0.55:
                            best_sim = sim
                            matched_session_unk = unk_item

                    if matched_session_unk:
                        track.unknown_db_id = matched_session_unk["db_id"]
                        track.unknown_crop_filename = matched_session_unk["crop_filename"]
                        track.best_quality = matched_session_unk["best_quality"]

                if not track.unknown_db_id:
                    # Genuinely new unknown person in session -> create 1 DB entry & 1 crop
                    unknown_count_ref[0] += 1
                    unk_filename = f"unk_person_{session_id[:8]}_{unknown_count_ref[0]}.jpg"
                    unk_path = os.path.join(UNKNOWN_FOLDER, unk_filename)
                    cv2.imwrite(unk_path, face_crop)

                    timestamp_str = f"{round(frame_number / fps, 2)}s" if fps > 0 else "0s"
                    unk_face = UnknownFace(
                        timestamp=timestamp_str,
                        frame_number=frame_number,
                        confidence=round(float(score), 2),
                        image_path=unk_filename,
                        status="New"
                    )
                    db.add(unk_face)
                    db.commit()

                    track.unknown_db_id = unk_face.id
                    track.best_quality = quality
                    track.unknown_crop_filename = unk_filename
                    unknown_delta += 1

                    if track.embedding is not None:
                        session_unknown_faces.append({
                            "embedding": track.embedding,
                            "db_id": unk_face.id,
                            "crop_filename": unk_filename,
                            "best_quality": quality
                        })
                elif quality > track.best_quality:
                    # Same unknown person, better quality frame -> overwrite SINGLE crop & update DB record
                    unk_filename = track.unknown_crop_filename
                    unk_path = os.path.join(UNKNOWN_FOLDER, unk_filename)
                    cv2.imwrite(unk_path, face_crop)

                    unk_obj = db.query(UnknownFace).filter(UnknownFace.id == track.unknown_db_id).first()
                    if unk_obj:
                        timestamp_str = f"{round(frame_number / fps, 2)}s" if fps > 0 else "0s"
                        unk_obj.timestamp = timestamp_str
                        unk_obj.frame_number = frame_number
                        unk_obj.confidence = round(float(score), 2)
                        db.commit()

                    track.best_quality = quality
                    # Update quality in session registry as well
                    for u in session_unknown_faces:
                        if u["db_id"] == track.unknown_db_id:
                            u["best_quality"] = quality
                            if track.embedding is not None:
                                u["embedding"] = track.embedding

    return annotated_frame, recognized_delta, unknown_delta


def _finalize_session(session_id, db, attendance_mgr, camera_name, attendance_date,
                       video_filename, total_frames, processed_count, recognized_count,
                       unknown_count, fps, width, height, start_time, output_video_path,
                       source_type):
    processing_time = round(time.time() - start_time, 2)

    attendance_mgr.save(camera_name, attendance_date)

    video_session = VideoSession(
        video_name=video_filename,
        camera_name=camera_name,
        attendance_date=attendance_date,
        total_frames=total_frames,
        processed_frames=processed_count,
        recognized_faces=recognized_count,
        unknown_faces=unknown_count,
        processing_time=processing_time,
        fps=round(fps, 2) if fps else 0,
        status="Completed",
        output_video_path=os.path.relpath(output_video_path, "static") if output_video_path else None,
        source_type=source_type,
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
        "recognized_faces": recognized_count,
        "unknown_faces": unknown_count,
        "records_marked": len(attendance_mgr.get_records()),
        "fps": round(fps, 2) if fps else 0,
        "resolution": f"{width}x{height}",
        "processing_time": processing_time,
        "output_video_url": f"/static/{video_session.output_video_path}" if video_session.output_video_path else None,
    }

    PROCESSING_STATUS[session_id] = {
        "status": "completed",
        "progress": 100,
        "result": result
    }

    return result


def analyze_video(video_path: str, camera_name: str, attendance_date: str, session_id: str = None):
    if not session_id:
        session_id = str(uuid.uuid4())

    cap = cv2.VideoCapture(video_path)

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

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "progress": 0,
        "current_frame": 0,
        "total_frames": total_frames,
        "recognized_faces": 0,
        "unknown_faces": 0,
        "start_time": time.time()
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
    session_unknown_faces = []
    session_identified_employees = {}

    tracker = ByteTracker()
    recognition_mgr = RecognitionManager(confirm_frames=1)
    attendance_mgr = AttendanceManager(camera_name=camera_name, attendance_date=attendance_date)

    db = SessionLocal()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1

            if frame_number % 3 != 0:
                writer.write(frame)
                continue

            processed_count += 1
            annotated_frame, rec_delta, unk_delta = _process_frame(
                frame, frame_number, fps, employees, attendance_mgr,
                tracker, recognition_mgr, session_id, db, unknown_count_ref,
                session_unknown_faces, session_identified_employees
            )
            recognized_count += rec_delta
            unknown_count += unk_delta

            writer.write(annotated_frame)

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
        writer.release()

    result = _finalize_session(
        session_id, db, attendance_mgr, camera_name, attendance_date, video_filename,
        total_frames, processed_count, recognized_count, unknown_count, fps, width, height,
        start_time, output_video_path, source_type="upload"
    )
    db.close()

    return result


def stream_uploaded_video(video_path: str, camera_name: str, attendance_date: str, session_id: str):
    yield from _stream_source(
        cap_source=video_path,
        camera_name=camera_name,
        attendance_date=attendance_date,
        session_id=session_id,
        video_filename=os.path.basename(video_path),
        source_type="upload",
        loop_forever=False,
    )


def stream_webcam(camera_index: int, camera_name: str, attendance_date: str, session_id: str):
    yield from _stream_source(
        cap_source=camera_index,
        camera_name=camera_name,
        attendance_date=attendance_date,
        session_id=session_id,
        video_filename=f"webcam_{camera_index}",
        source_type="webcam",
        loop_forever=True,
    )


def _stream_source(cap_source, camera_name, attendance_date, session_id,
                    video_filename, source_type, loop_forever):
    STREAM_CONTROL[session_id] = {"stop": False}

    cap = cv2.VideoCapture(cap_source)
    if source_type == "webcam":
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        PROCESSING_STATUS[session_id] = {"status": "failed", "message": "Cannot open video source."}
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if source_type == "upload" else 0

    PROCESSING_STATUS[session_id] = {
        "status": "processing",
        "progress": 0,
        "current_frame": 0,
        "total_frames": total_frames,
        "recognized_faces": 0,
        "unknown_faces": 0,
        "start_time": time.time()
    }

    attendance_mgr = AttendanceManager(camera_name=camera_name, attendance_date=attendance_date)
    tracker = ByteTracker()
    recognition_mgr = RecognitionManager(confirm_frames=1)

    employees = load_embeddings()
    _ensure_folders()

    writer, output_video_path = _make_writer(session_id, width, height, fps)

    start_time = time.time()
    frame_number = 0
    processed_count = 0
    recognized_count = 0
    unknown_count = 0
    unknown_count_ref = [0]
    session_unknown_faces = []
    session_identified_employees = {}

    db = SessionLocal()

    try:
        while True:
            if STREAM_CONTROL.get(session_id, {}).get("stop"):
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1

            if frame_number % 3 == 0:
                processed_count += 1
                annotated_frame, rec_delta, unk_delta = _process_frame(
                    frame, frame_number, fps, employees, attendance_mgr,
                    tracker, recognition_mgr, session_id, db, unknown_count_ref,
                    session_unknown_faces, session_identified_employees
                )
                recognized_count += rec_delta
                unknown_count += unk_delta
            else:
                annotated_frame = frame

            writer.write(annotated_frame)

            progress_pct = (
                int((frame_number / total_frames) * 100) if total_frames > 0 else 0
            )
            PROCESSING_STATUS[session_id].update({
                "progress": progress_pct,
                "current_frame": frame_number,
                "recognized_faces": recognized_count,
                "unknown_faces": unknown_count
            })

            ok, buffer = cv2.imencode(".jpg", annotated_frame)
            if not ok:
                continue

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

    except GeneratorExit:
        pass
    except Exception as e:
        print(f"[VideoService] Error during live stream: {e}")
    finally:
        cap.release()
        writer.release()
        STREAM_CONTROL.pop(session_id, None)

        _finalize_session(
            session_id, db, attendance_mgr, camera_name, attendance_date, video_filename,
            total_frames or frame_number, processed_count, recognized_count, unknown_count,
            fps, width, height, start_time, output_video_path, source_type=source_type
        )
        db.close()


