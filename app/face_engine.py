import cv2
import numpy as np
from insightface.app import FaceAnalysis

# Initialize model once
app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(ctx_id=0, det_size=(640, 640))


import cv2

def get_faces(image_path):
    img = cv2.imread(image_path)

    if img is None:
        print(f"Cannot read image: {image_path}")
        return []

    print("Image shape:", img.shape)

    faces = app.get(img)

    print(f"Faces detected: {len(faces)}")

    return faces

def validate_face(image_path):
    """
    Returns:
    OK, embedding
    NO_FACE, None
    MULTIPLE_FACES, None
    """

    faces = get_faces(image_path)

    if len(faces) == 0:
        return "NO_FACE", None

    if len(faces) > 1:
        return "MULTIPLE_FACES", None

    return "OK", faces[0].embedding


def get_embedding(image_path):
    status, embedding = validate_face(image_path)
    return embedding

