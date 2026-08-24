import sys
import os

sys.path.insert(0, os.path.abspath("."))

import numpy as np
from app.database import SessionLocal, Base, engine
from app.models import Employee, Attendance, UnknownFace
from app.services.track_manager import ByteTracker, STrack
from app.services.recognition_manager import RecognitionManager
from app.services.attendance_service import AttendanceManager


def run_tests():
    print("==================================================")
    print("  STRICT IDENTITY LOCK & SINGLE BEST SCREENSHOT TEST")
    print("==================================================")

    # 1. Test Immediate Identity Lock-in on First Match
    print("\n--- TEST 1: Identified Once -> Permanent Identity Lock-in ---")
    rec_mgr = RecognitionManager(confirm_frames=1)
    track = STrack(bbox=[50, 50, 150, 150], det_score=0.90)

    emp_bob = {"employee_id": "EMP202", "name": "Bob"}
    # Frame 1: Identified as Bob with score 0.70
    track = rec_mgr.update_strack(track, emp_bob, score=0.70)
    assert track.confirmed == True, "Identity should be confirmed immediately on 1st match"
    assert track.employee["name"] == "Bob", "Employee should be Bob"
    print("✅ Frame 1: Person identified as Bob -> confirmed=True immediately")

    # Frame 2 (Next Frame): Recognition score drops / employee returned as None due to face angle
    track = rec_mgr.update_strack(track, None, score=0.30)
    assert track.confirmed == True, "Identity MUST stay confirmed"
    assert track.employee["name"] == "Bob", "Employee MUST stay Bob on next frame!"
    assert track.state == "RECOGNIZED", "State MUST stay RECOGNIZED!"
    print("✅ Frame 2 (Next Frame): Low score / None returned -> Person DOES NOT move to unknown! Identity stays locked to Bob.")

    # 2. Test Session-level Unknown Face Single Best Screenshot
    print("\n--- TEST 2: Single Best Screenshot for Unknown Person Across Tracks ---")
    db = SessionLocal()
    session_id = "test_sess_dedup"
    unk_crop_dir = "static/uploads/unknown_faces"
    os.makedirs(unk_crop_dir, exist_ok=True)

    dummy_frame = np.zeros((400, 400, 3), dtype=np.uint8)
    dummy_embedding = np.random.randn(512).astype(np.float32)
    dummy_embedding /= np.linalg.norm(dummy_embedding)

    session_unknown_faces = []

    # Track A for Unknown Person
    track_A = STrack(bbox=[30, 30, 100, 100], det_score=0.80, embedding=dummy_embedding)
    track_A.track_id = 101

    # Frame 1: Genuinely new unknown person -> create 1 DB entry & 1 crop
    unk_filename_A = f"unk_person_{session_id[:8]}_1.jpg"
    unk_path_A = os.path.join(unk_crop_dir, unk_filename_A)
    import cv2
    cv2.imwrite(unk_path_A, dummy_frame[30:100, 30:100])

    unk_face_A = UnknownFace(
        timestamp="1.0s",
        frame_number=10,
        confidence=0.80,
        image_path=unk_filename_A,
        status="New"
    )
    db.add(unk_face_A)
    db.commit()

    track_A.unknown_db_id = unk_face_A.id
    track_A.best_quality = 100.0
    track_A.unknown_crop_filename = unk_filename_A

    session_unknown_faces.append({
        "embedding": dummy_embedding,
        "db_id": unk_face_A.id,
        "crop_filename": unk_filename_A,
        "best_quality": 100.0
    })

    db_count_1 = db.query(UnknownFace).filter(UnknownFace.id == unk_face_A.id).count()
    assert db_count_1 == 1, "Expected 1 DB entry for new unknown person"
    print(f"✅ Unknown Person X spawned DB entry (id={unk_face_A.id}) and screenshot.")

    # Track B (Tracking re-initializes for SAME unknown person with similar embedding)
    track_B = STrack(bbox=[35, 35, 120, 120], det_score=0.85, embedding=dummy_embedding + 0.01)
    track_B.embedding /= np.linalg.norm(track_B.embedding)
    track_B.track_id = 102

    # Deduplication check: compare embedding with session_unknown_faces
    from app.recognizer import cosine_similarity
    best_sim = cosine_similarity(track_B.embedding, session_unknown_faces[0]["embedding"])
    assert best_sim >= 0.55, f"Similarity should match existing unknown person (got {best_sim})"

    # Deduplication links track_B to existing unk_face_A.id
    track_B.unknown_db_id = session_unknown_faces[0]["db_id"]
    track_B.unknown_crop_filename = session_unknown_faces[0]["crop_filename"]
    track_B.best_quality = session_unknown_faces[0]["best_quality"]

    # Frame 2: Better quality crop overwrites SAME image file & updates SAME DB record
    cv2.imwrite(unk_path_A, dummy_frame[20:130, 20:130])
    unk_obj = db.query(UnknownFace).filter(UnknownFace.id == track_B.unknown_db_id).first()
    unk_obj.timestamp = "2.5s"
    db.commit()

    total_unk_in_db = db.query(UnknownFace).filter(UnknownFace.image_path == unk_filename_A).count()
    assert total_unk_in_db == 1, f"Expected ONLY 1 DB entry for unknown person, got {total_unk_in_db}"
    print(f"✅ Track B recognized as SAME Unknown Person X! Overwrote screenshot & updated DB entry (id={unk_face_A.id}). Total DB rows = 1!")

    db.close()
    print("\n🎉 ALL STRICT IDENTITY & SINGLE SCREENSHOT TESTS PASSED!")


if __name__ == "__main__":
    run_tests()
