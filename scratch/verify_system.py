import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath("."))

from app.storage import init_db
from app.database import SessionLocal
from app.models import Employee, EmployeeImage, Attendance, UnknownFace, VideoSession
from app.services.embedding_service import load_embeddings
from app.recognizer import recognize
import numpy as np

def run_tests():
    print("--- STEP 1: Testing DB Table Creation ---")
    init_db()
    print("✅ DB tables initialized successfully.")

    print("\n--- STEP 2: Testing Models & Queries ---")
    db = SessionLocal()
    emp_count = db.query(Employee).count()
    att_count = db.query(Attendance).count()
    sess_count = db.query(VideoSession).count()
    unk_count = db.query(UnknownFace).count()
    db.close()
    print(f"✅ DB Counts: Employees={emp_count}, Attendance={att_count}, VideoSessions={sess_count}, UnknownFaces={unk_count}")

    print("\n--- STEP 3: Testing Embedding Cache Service ---")
    embeddings = load_embeddings(force_reload=True)
    print(f"✅ Loaded {len(embeddings)} face embeddings.")

    print("\n--- STEP 4: Testing Cosine Recognition Logic ---")
    if len(embeddings) > 0:
        dummy_face = embeddings[0]["embedding"]
        matched_emp, score = recognize(dummy_face, embeddings)
        print(f"✅ Matched: {matched_emp['name']} with score {score:.4f}")
    else:
        dummy_face = np.zeros((512,), dtype=np.float32)
        matched_emp, score = recognize(dummy_face, embeddings)
        print(f"✅ Recognition handled empty/zero embedding gracefully. Best score: {score:.4f}")

    print("\n--- STEP 5: Testing Router Imports & FastAPI App ---")
    from app.main import app
    print(f"✅ FastAPI App successfully initialized with routes:")
    for route in app.routes:
        if hasattr(route, "path"):
            print(f"   - {route.methods if hasattr(route, 'methods') else 'GET'} {route.path}")

    print("\n🎉 ALL BACKEND CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
