import sys
import os

sys.path.insert(0, os.path.abspath("."))

import cv2
import numpy as np
from app.face_engine import app as face_model
from app.services.embedding_service import load_embeddings
from app.recognizer import recognize, cosine_similarity
from app.database import SessionLocal
from app.models import Employee, EmployeeImage, Attendance, UnknownFace


def diagnose():
    video_dir = "static/uploads/video"
    video_files = [f for f in os.listdir(video_dir) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]

    if not video_files:
        print("❌ No video file found in static/uploads/video")
        return

    video_path = os.path.join(video_dir, video_files[0])
    print(f"🎬 Diagnosing video: {video_path}")

    # Load registered employees and embeddings
    employees = load_embeddings(force_reload=True)
    print(f"👥 Registered Employees loaded: {len(employees)}")

    db = SessionLocal()
    db_employees = db.query(Employee).all()
    print(f"DB Employee Records ({len(db_employees)}):")
    for emp in db_employees:
        img_count = db.query(EmployeeImage).filter(EmployeeImage.employee_ref == emp.id).count()
        print(f"  - [{emp.employee_id}] {emp.name} (Images registered: {img_count})")
    db.close()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Failed to open video: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    print(f"📹 Total frames: {total_frames}, FPS: {fps}")

    frame_num = 0
    detections_summary = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1
        if frame_num % 5 != 0:
            continue

        faces = face_model.get(frame)
        if len(faces) == 0:
            continue

        print(f"\n--- Frame {frame_num} / {total_frames} (Faces detected: {len(faces)}) ---")

        for idx, face in enumerate(faces):
            bbox = face.bbox.astype(int)
            det_score = getattr(face, "det_score", 1.0)
            emb = face.embedding

            # Check similarity with all registered embeddings
            scores_per_emp = []
            for emp in employees:
                sim = cosine_similarity(emb, emp["embedding"])
                scores_per_emp.append((emp["name"], emp["employee_id"], sim))

            scores_per_emp.sort(key=lambda x: x[2], reverse=True)

            best_emp, best_id, best_score = scores_per_emp[0] if scores_per_emp else ("None", "None", 0.0)
            recognized_emp, rec_score = recognize(emb, employees)

            status = "GREEN (Known)" if recognized_emp else "RED (Unknown)"
            print(f"  Face #{idx+1}: BBox={bbox.tolist()}, DetScore={det_score:.2f} -> Best Match: {best_emp} ({best_score:.4f}) => {status}")

            detections_summary.append({
                "frame": frame_num,
                "face_idx": idx + 1,
                "det_score": float(det_score),
                "best_emp": best_emp,
                "best_score": float(best_score),
                "recognized": recognized_emp is not None
            })

    cap.release()

    known_count = sum(1 for d in detections_summary if d["recognized"])
    unknown_count = sum(1 for d in detections_summary if not d["recognized"])
    print("\n==================================================")
    print("  DIAGNOSIS SUMMARY FOR CCTV VIDEO")
    print("==================================================")
    print(f"Total Detected Faces evaluated: {len(detections_summary)}")
    print(f"Known Detections (Green): {known_count}")
    print(f"Unknown Detections (Red): {unknown_count}")

    if detections_summary:
        all_scores = [d["best_score"] for d in detections_summary]
        print(f"Max Similarity Score across all faces: {max(all_scores):.4f}")
        print(f"Min Similarity Score across all faces: {min(all_scores):.4f}")
        print(f"Average Similarity Score across all faces: {np.mean(all_scores):.4f}")


if __name__ == "__main__":
    diagnose()
