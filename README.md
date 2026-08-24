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

- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLAlchemy, SQLite
- **AI & Computer Vision**: InsightFace (`buffalo_l`), OpenCV, NumPy
- **Frontend**: HTML5, CSS3 , JavaScript

---

## 📁 Directory Structure

```
AI_Attendance_System/
├── app/
│   ├── database.py              # SQLite database engine & session creation
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
├── static/
│   ├── css/
│   │   └── styles.css           # Custom enterprise dark design system
│   ├── js/
│   │   └── app.js               # Toast notifications, modals, image lightbox
│   ├── screenshots/             # Saved attendance screenshot proofs
│   └── uploads/
│       ├── employees/           # Enrolled employee face profile photos
│       ├── unknown_faces/       # Unknown face crop snapshots
│       └── video/               # Uploaded CCTV video files
├── templates/
│   ├── add_employee.html        # Employee registration form with dropzone
│   ├── attendance.html          # Filterable attendance log page
│   ├── base.html                # Master layout template (header + sidebar)
│   ├── dashboard.html           # Simple professional dashboard
│   ├── employees.html           # Employee catalog directory
│   ├── process_video.html       # CCTV video upload & progress tracking
│   └── unknown_faces.html       # Unknown face alert gallery
├── attendance.db                # SQLite Database file
├── requirements.txt             # Python dependencies
└── README.md                    # System documentation
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
Ensure you have **Python 3.10+** installed on your system.

### 2. Clone / Setup Project Directory
```bash
cd /path/to/AI_Attendance_System
```

### 3. Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 💻 Running the Web Application

Start the Uvicorn development server:

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
