import sys
import os

sys.path.insert(0, os.path.abspath("."))

import cv2
import numpy as np
from app.face_engine import app as face_model
from app.services.embedding_service import load_embeddings
from app.recognizer import cosine_similarity


def test_detailed():
    video_path = "static/uploads/video/WhatsApp Video 2026-08-07 at 12.25.35 PM (1).mp4"
    employees = load_embeddings(force_reload=True)

    cap = cv2.VideoCapture(video_path)

    session_identified_employees = {} # emp_id -> info
    frame_num = 0

    known_count = 0
    unknown_count = 0
    unknown_details = []

    CCTV_THRESHOLD = 0.45
    SESSION_LOCK_THRESHOLD = 0.35

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1
        if frame_num % 3 != 0:
            continue

        faces = face_model.get(frame)
        for face in faces:
            emb = face.embedding

            best_emp = None
            best_score = -1.0

            for emp in employees:
                sim = cosine_similarity(emb, emp["embedding"])
                if sim > best_score:
                    best_score = sim
                    best_emp = emp

            matched = None
            if best_score >= CCTV_THRESHOLD:
                matched = best_emp
                session_identified_employees[best_emp["employee_id"]] = best_emp
            elif best_emp and best_emp["employee_id"] in session_identified_employees:
                if best_score >= SESSION_LOCK_THRESHOLD:
                    matched = best_emp

            if matched:
                known_count += 1
            else:
                unknown_count += 1
                unknown_details.append({
                    "frame": frame_num,
                    "bbox": face.bbox.astype(int).tolist(),
                    "det_score": float(face.det_score),
                    "best_emp": best_emp["name"] if best_emp else "None",
                    "best_score": float(best_score)
                })

    cap.release()

    print("\n==================================================")
    print("  DETAILED CCTV TEST (CCTV_THRESH=0.45, LOCK_THRESH=0.35)")
    print("==================================================")
    print(f"Total Evaluated Face Detections: {known_count + unknown_count}")
    print(f"Known Detections (Green): {known_count} ({known_count / (known_count + unknown_count) * 100:.1f}%)")
    print(f"Unknown Detections (Red): {unknown_count} ({unknown_count / (known_count + unknown_count) * 100:.1f}%)")
    print(f"Identified Employees: {[e['name'] for e in session_identified_employees.values()]}")

    print("\nSample Remaining Unknown Detections (First 15):")
    for unk in unknown_details[:15]:
        print(f"  Frame {unk['frame']}: BBox={unk['bbox']}, DetScore={unk['det_score']:.2f} -> Best Match: {unk['best_emp']} ({unk['best_score']:.4f})")


if __name__ == "__main__":
    test_detailed()
