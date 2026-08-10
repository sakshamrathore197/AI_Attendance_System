import numpy as np

from app.face_engine import get_embedding


from app.face_engine import validate_face

status, embedding = validate_face(
    "/Users/sakshamrathore/Quality_Webs/AI_Attendance_System/static/uploads/employees/1/Photo on 07-08-26 at 2.51 PM.jpg"
)

print(status)