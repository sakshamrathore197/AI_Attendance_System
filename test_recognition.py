import numpy as np

from app.database import SessionLocal
from app.face_engine import validate_face
from app.recognizer import recognize

db = SessionLocal()

status, embedding = validate_face("/Users/sakshamrathore/Quality_Webs/AI_Attendance_System/pitti.jpg")

if status != "OK":
    print("Face not detected.")
    exit()

result = recognize(
    embedding,
    db
)

print(result)

db.close()