import numpy as np
from app.database import SessionLocal
from app.models import EmployeeImage, Employee

_EMBEDDINGS_CACHE = None

def load_embeddings(force_reload: bool = False):
    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is not None and not force_reload:
        return _EMBEDDINGS_CACHE

    db = SessionLocal()
    employees = []
    try:
        rows = db.query(EmployeeImage).all()
        for row in rows:
            if not row.employee or row.employee.status == "Inactive":
                continue
            employees.append({
                "employee_id": row.employee.employee_id,
                "name": row.employee.name,
                "department": row.employee.department or "General",
                "embedding": np.frombuffer(
                    row.embedding,
                    dtype=np.float32
                )
            })
        _EMBEDDINGS_CACHE = employees
        print(f"[EmbeddingService] Loaded {len(employees)} active embeddings into cache.")
    except Exception as e:
        print(f"[EmbeddingService] Error loading embeddings: {e}")
    finally:
        db.close()

    return _EMBEDDINGS_CACHE

def clear_embedding_cache():
    global _EMBEDDINGS_CACHE
    _EMBEDDINGS_CACHE = None