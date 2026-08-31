# 🎥 AI CCTV Video Attendance System

An automated, AI-powered Face Recognition Attendance System built with **FastAPI**, **OpenCV**, **InsightFace**, **SQLAlchemy**, and a clean enterprise Web Dashboard. The system processes CCTV footage and video streams to detect, identify, and log employee attendance automatically with bounding box screenshot proofs and unknown face detection alerts.

---

## 🌟 Key Features

- **💼 Simple & Professional Executive Dashboard**:
  - Top KPI stat cards for Total Active Staff, Today's Attendance %, Videos Processed, and Unknown Face Alerts.
  - Side-by-side data tables for **Today's Verified Attendance** and **CCTV Video Processing Sessions**.
  - Direct action bar for uploading video footage or enrolling new employees.

- **📹 CCTV Video Processor**:
  - Asynchronous background video file analysis (`.mp4`, `.avi`, `.mov`, `.mkv`).
  - Real-time progress tracking API with animated progress bar polling.
  - Bounding box annotations and confidence score labels drawn directly onto saved screenshot proofs.

- **🤖 Deep Learning Face Recognition Engine**:
  - InsightFace (`buffalo_l` deep neural network model) producing 512-dimensional face feature vectors.
  - Cosine Similarity threshold matching against pre-computed face embeddings.
  - Automatic thread-safe in-memory embedding caching.

- **👥 Employee Directory & Face Enrollment**:
  - Searchable employee directory grid/table with department filtering.
  - Multi-photo drag-and-drop face profile registration with automatic face detection validation.

- **📋 Attendance Logs & CSV Export**:
  - Detailed logs with First-Seen timestamp, Last-Seen timestamp, Total Frame Count, and Status (`Present`).
  - Filter by date, employee name/ID, and camera location source.
  - One-click **CSV Report Export** functionality.
  - Screenshot proof lightbox viewer.

- **🚨 Unknown Face Alert Center**:
  - Log of unrecognized face crops captured from CCTV streams.
  - One-click modal to assign unknown faces to existing employee profiles.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLAlchemy
- **Database**: PostgreSQL (Production) / SQLite (Development fallback)
- **AI & Computer Vision**: InsightFace (`buffalo_l`), OpenCV, NumPy
- **Containerization**: Docker, Docker Compose
- **Frontend**: HTML5, CSS3, JavaScript

---

## 📁 Directory Structure

```
AI_Attendance_System/
├── app/
│   ├── database.py              # PostgreSQL & SQLite database engine & session creation
│   ├── face_engine.py           # InsightFace model loader & face validator
│   ├── main.py                  # FastAPI application entry point & router registration
│   ├── models.py                # SQLAlchemy ORM models (Employee, Attendance, etc.)
│   ├── recognizer.py            # Cosine similarity face recognizer
│   ├── storage.py               # Database table initialization & migrations
│   ├── routers/
│   │   ├── attendance.py        # Attendance log views, CSV export, manual override
│   │   ├── dashboard.py         # Dashboard page & stats JSON API
│   │   ├── employees.py         # Employee CRUD & multi-image face enrollment
│   │   ├── unknown_faces.py     # Unknown face log & assignment API
│   │   └── video.py             # CCTV video upload, processing, status polling
│   └── services/
│       ├── attendance_service.py # Session-aware attendance manager
│       ├── embedding_service.py  # Thread-safe cached face embeddings loader
│       └── video_service.py     # Background CCTV video frame processing worker
├── docker-compose.yml           # Multi-container Docker setup (App + PostgreSQL)
├── Dockerfile                   # App container build definition
├── .env.example                 # Environment variables configuration template
├── requirements.txt             # Python dependencies
└── README.md                    # System documentation
```

---

## 🚀 Quick Start & Installation

### Option A: Running with Docker Compose (Recommended - includes PostgreSQL)

1. Clone / navigate to the project directory:
   ```bash
   cd /path/to/AI_Attendance_System
   ```

2. Start the application and PostgreSQL database:
   ```bash
   docker compose up --build
   ```

3. Open your browser at:
   👉 **[http://localhost:8000](http://localhost:8000)**

---

### Option B: Running Locally

#### 1. Prerequisites
Ensure you have **Python 3.10+** and optionally **PostgreSQL** installed.

#### 2. Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Database
Copy `.env.example` to `.env` and configure your database:
```bash
cp .env.example .env
```

- **For PostgreSQL**:
  ```env
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/attendance_db
  ```
- **For SQLite** (default fallback if `DATABASE_URL` is omitted):
  ```env
  DATABASE_URL=sqlite:///attendance.db
  ```

#### 5. Start Application
```bash
uvicorn app.main:app --port 8000 --reload
```


Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 📖 How It Works

1. **Register Employees**:
   - Navigate to `/employees/add`.
   - Enter Employee ID, Name, Department, and upload 1-5 clear face photos.
   - The AI face engine validates single-face presence and extracts 512-d feature vectors.

2. **Process CCTV Video**:
   - Navigate to `/video/process`.
   - Select a CCTV footage file (`.mp4`, `.mov`, etc.), specify camera location name and attendance date.
   - Click **Start AI Analysis**. The background worker processes frames, matches faces against cached embeddings, draws green bounding boxes, and records attendance.

3. **View & Export Attendance**:
   - Navigate to `/attendance` to view verified records and preview screenshot proofs.
   - Click **Export CSV** to download attendance reports.

4. **Review Unknown Faces**:
   - Navigate to `/unknown-faces` to review unassigned face crops and assign them to employees with one click.

---

## 📄 License

This project is open source and available under the **MIT License**.
