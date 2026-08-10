import numpy as np
from sqlalchemy.orm import Session

from app.models import EmployeeImage


# Recognition Threshold
THRESHOLD = 0.60


def cosine_similarity(a, b):
    """
    Returns cosine similarity between two embeddings.
    """

    a = a.astype(np.float32)
    b = b.astype(np.float32)

    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )


def recognize(face_embedding, employees):

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
    
    print(f"Best Score: {best_score:.4f}")
    if best_score >= THRESHOLD:
        return best_employee, best_score

    return None, best_score