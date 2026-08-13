import numpy as np
from sqlalchemy.orm import Session

from app.models import EmployeeImage


# Recognition Threshold (Optimized for CCTV & Low-Res Video Streams)
THRESHOLD = 0.45


def cosine_similarity(a, b):
    """
    Returns cosine similarity between two embeddings.
    """

    a = a.astype(np.float32)
    b = b.astype(np.float32)

    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )


def recognize(face_embedding, employees, session_employees=None):
    best_score = -1
    best_employee = None

    for emp in employees:
        score = cosine_similarity(
            face_embedding,
            emp["embedding"]
        )

        if score > best_score:
            best_score = score
            best_employee = emp

    # Check if matched against an employee already identified in session (lower threshold for continuous tracking)
    effective_thresh = THRESHOLD
    if session_employees and best_employee and best_employee["employee_id"] in session_employees:
        effective_thresh = 0.35

    if best_score >= effective_thresh:
        return best_employee, best_score

    return None, best_score