import os
import numpy as np
import cv2
from datetime import datetime

from app.storage import init_db
from app.database import SessionLocal
from app.models import UnknownFace
from app.services.video_service import _process_unknown_face_dedup, _SESSION_UNKNOWN_TRACKS


class DummyFace:
    def __init__(self, embedding, bbox, det_score=0.90):
        self.embedding = np.array(embedding, dtype=np.float32)
        self.bbox = bbox
        self.det_score = det_score


def run_tests():
    print("=== TEST: Unknown Face Deduplication & Best Crop Overwriting ===")
    init_db()
    db = SessionLocal()

    try:
        # Clear existing unknown tracks & table for clean test run
        _SESSION_UNKNOWN_TRACKS.clear()

        # Dummy frame image (100x100 RGB canvas)
        dummy_frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_frame1[:, :] = (255, 0, 0) # Blue canvas

        dummy_frame2 = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_frame2[:, :] = (0, 255, 0) # Green canvas (higher quality frame)

        # Unknown Person 1 (512-dim vector centered around 1.0)
        emb_person1 = np.random.randn(512).astype(np.float32)
        emb_person1 /= np.linalg.norm(emb_person1)

        face_frame1 = DummyFace(emb_person1, [10, 10, 50, 50], det_score=0.70)

        session_id = "test_unk_session_01"
        unknown_ref = [0]

        # --- Frame 1: First time Unknown Person 1 appears ---
        is_new1 = _process_unknown_face_dedup(
            face_frame1, dummy_frame1, frame_number=1, fps=25.0,
            camera_id="cam_test", session_id=session_id, db=db, unknown_count_ref=unknown_ref
        )
        db.commit()

        print(f"Frame 1 - New Unknown Record Created: {is_new1}")
        assert is_new1 is True, "First occurrence of unknown face must create a record"

        rec1 = db.query(UnknownFace).filter(UnknownFace.camera_id == "cam_test").order_by(UnknownFace.id.desc()).first()
        rec1_id = rec1.id
        print(f"Record 1 ID: {rec1_id}, Seen Count: {rec1.seen_count}, Confidence: {rec1.confidence}")
        assert rec1.seen_count == 1, "Initial seen_count should be 1"

        # --- Frame 2: Same Unknown Person 1 appears with slight embedding noise ---
        emb_person1_noise = emb_person1 + (np.random.randn(512).astype(np.float32) * 0.02)
        emb_person1_noise /= np.linalg.norm(emb_person1_noise)

        face_frame2 = DummyFace(emb_person1_noise, [5, 5, 80, 80], det_score=0.95) # Larger bbox & higher quality score

        is_new2 = _process_unknown_face_dedup(
            face_frame2, dummy_frame2, frame_number=2, fps=25.0,
            camera_id="cam_test", session_id=session_id, db=db, unknown_count_ref=unknown_ref
        )
        db.commit()

        print(f"Frame 2 - New Unknown Record Created: {is_new2}")
        assert is_new2 is False, "Same unknown person MUST NOT create a new duplicate record in another frame!"

        rec2 = db.query(UnknownFace).filter(UnknownFace.id == rec1_id).first()
        print(f"Record 1 After Frame 2 - Seen Count: {rec2.seen_count}, Updated Confidence: {rec2.confidence}")
        assert rec2.seen_count == 2, "seen_count should increment to 2"
        assert rec2.confidence == 0.95, "Confidence score should update to higher quality score (0.95)"

        # --- Frame 3: Distinct Unknown Person 2 appears ---
        emb_person2 = np.random.randn(512).astype(np.float32)
        emb_person2 /= np.linalg.norm(emb_person2)
        face_person2 = DummyFace(emb_person2, [20, 20, 60, 60], det_score=0.88)

        is_new3 = _process_unknown_face_dedup(
            face_person2, dummy_frame1, frame_number=3, fps=25.0,
            camera_id="cam_test", session_id=session_id, db=db, unknown_count_ref=unknown_ref
        )
        db.commit()

        print(f"Frame 3 (Distinct Person) - New Unknown Record Created: {is_new3}")
        assert is_new3 is True, "Distinct unknown person MUST create a new record"

        print("\n=============================================")
        print("UNKNOWN DEDUPLICATION TESTS PASSED CLEANLY! ✓")
        print("=============================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
