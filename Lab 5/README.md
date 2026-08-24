# Lab 5 — Failure and Recovery Test

## Goal
Demonstrate and prove that the AI Attendance System and RTSP ingestion layer gracefully handle **sudden camera disconnects / stream interruptions** and **automatically recover** without crashing or requiring a server restart.

---

## 4-Phase Test Execution

1. **Phase 1: Baseline Connection**
   - Connects to the active RTSP source (`rtsp://localhost:8554/entrance`).
   - Verifies healthy video frame acquisition.

2. **Phase 2: Simulated Camera/Network Failure**
   - Simulates physical camera disconnect or network outage by killing the publisher process (`pkill -f "rtsp://localhost:8554"`).
   - Validates that the system catches the stream drop (`cap.isOpened() == False` or `cap.read() == False`) without crashing.

3. **Phase 3: Stream Restoration**
   - Restores the camera stream publisher.

4. **Phase 4: Automatic Reconnection & Validation**
   - Verifies that the client auto-reconnects, pulls valid video frames, and resumes normal processing.

---

## Running the Test
```bash
source .venv/bin/activate
python3 "Lab 5/test_failure_recovery.py"
```
