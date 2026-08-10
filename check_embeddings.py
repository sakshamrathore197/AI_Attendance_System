from app.database import SessionLocal
from app.models import EmployeeImage
import numpy as np

db = SessionLocal()

rows = db.query(EmployeeImage).all()

print(f"Total Images: {len(rows)}")

for row in rows:
    emb = np.frombuffer(row.embedding, dtype=np.float32)

    print("Image:", row.image_path)
    print("Embedding Shape:", emb.shape)
    print("-" * 40)

db.close()
