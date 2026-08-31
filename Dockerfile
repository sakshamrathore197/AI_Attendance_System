# Dockerfile
# For sakshamrathore197/AI_Attendance_System — FastAPI + OpenCV + InsightFace
# (buffalo_l, ONNX Runtime) + SQLAlchemy/SQLite.
#
# Place this file in the repo ROOT (same level as requirements.txt, app/,
# static/, templates/).
#
# No dlib/cmake needed here (that was a different stack) — InsightFace ships
# as prebuilt ONNX models run through onnxruntime, so this build is lighter
# and faster than a face_recognition/dlib image.

FROM python:3.11-slim

# --- System libraries OpenCV/onnxruntime need at runtime ---
# (libgl1/libglib2.0-0: OpenCV's imshow/highgui deps even in headless use;
#  ffmpeg: needed to decode .mp4/.avi/.mov/.mkv uploads via cv2.VideoCapture)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python dependencies (cached as their own layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- App code ---
COPY . .

# InsightFace downloads its buffalo_l model weights to ~/.insightface on
# first use if not already cached. Pre-warming it here means the model is
# baked into the image instead of downloading on every fresh container -
# comment this out if you'd rather download at first run / via volume.
RUN python3 -c "from insightface.app import FaceAnalysis; fa = FaceAnalysis(name='buffalo_l'); fa.prepare(ctx_id=-1)" || true

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
