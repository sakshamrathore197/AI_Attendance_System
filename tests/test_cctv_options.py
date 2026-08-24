import os
import io
import time
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import (
    Employee,
    Attendance,
    AttendanceEvent,
    AttendanceInterval,
    AttendanceSession,
    VideoSession,
    UnknownFace,
)
from app.services.video_service import request_stream_stop, ACTIVE_CAPTURES, _INOUT_ENGINE
from app.services.inout_engine import InOutEngine


def run_tests():
    client = TestClient(app)
    print("=== TEST 1: Processor Page Renders 3 Clean Options ===")
    res = client.get("/video/process")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text
    assert "1. Live CCTV RTSP (MediaMTX)" in html
    assert "2. Uploaded Video" in html
    assert "3. Testing via Webcam" in html
    assert "rtsp://localhost:8554/live" in html
    assert "Auto-reconnect Enabled" in html
    print("✓ Processor HTML renders all 3 dedicated modes and MediaMTX presets.")

    print("\n=== TEST 2: Connection Test Endpoint ===")
    res_test = client.post("/video/test-connection", data={"camera_type": "rtsp", "url_or_index": "rtsp://localhost:8554/invalid"})
    assert res_test.status_code == 200
    data_test = res_test.json()
    print("✓ RTSP test response:", data_test)
    assert not data_test["status"]

    print("\n=== TEST 3: Prepare Endpoints for all 3 Modes ===")
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Mode 1: RTSP Prepare
    res_rtsp = client.post("/video/rtsp/prepare", data={
        "rtsp_url": "rtsp://localhost:8554/live",
        "camera_name": "Gate 1 RTSP",
        "direction": "IN",
        "attendance_date": today_str
    })
    assert res_rtsp.status_code == 200
    data_rtsp = res_rtsp.json()
    assert data_rtsp["status"] and "session_id" in data_rtsp
    rtsp_sid = data_rtsp["session_id"]
    print("✓ RTSP prepare success. Session ID:", rtsp_sid)

    # Mode 2: Upload Prepare with Direction
    dummy_video = io.BytesIO(b"dummy video data")
    res_upload = client.post("/video/stream/prepare", data={
        "camera_name": "Gate 2 Recorded CCTV",
        "direction": "OUT",
        "attendance_date": today_str
    }, files={"file": ("test_cctv.mp4", dummy_video, "video/mp4")})
    assert res_upload.status_code == 200
    data_upload = res_upload.json()
    assert data_upload["status"] and "session_id" in data_upload
    upload_sid = data_upload["session_id"]
    print("✓ Upload prepare success with OUT direction. Session ID:", upload_sid)

    # Mode 3: Webcam Prepare with Direction
    res_webcam = client.post("/video/webcam/prepare", data={
        "camera_index": "0",
        "camera_name": "Front Desk Webcam",
        "direction": "IN",
        "attendance_date": today_str
    })
    assert res_webcam.status_code == 200
    data_webcam = res_webcam.json()
    assert data_webcam["status"] and "session_id" in data_webcam
    webcam_sid = data_webcam["session_id"]
    print("✓ Webcam prepare success with IN direction. Session ID:", webcam_sid)

    print("\n=== TEST 4: Stop Stream & Hardware Release ===")
    res_stop_1 = client.post(f"/video/stream/stop/{upload_sid}")
    assert res_stop_1.status_code == 200
    assert res_stop_1.json()["status"]

    res_stop_2 = client.post(f"/video/webcam/stop/{webcam_sid}")
    assert res_stop_2.status_code == 200
    assert res_stop_2.json()["status"]

    res_stop_3 = client.post(f"/video/rtsp/stop/{rtsp_sid}")
    assert res_stop_3.status_code == 200
    assert res_stop_3.json()["status"]
    print("✓ Universal stop endpoints successfully signal and release hardware captures.")

    print("\n=== TEST 5: Real-time Attendance & IN/OUT Direction Deduplication Persistence ===")
    db = SessionLocal()
    test_emp_id = f"EMP-CCTV-{int(time.time())}"
    emp_record = Employee(
        employee_id=test_emp_id,
        name="CCTV Test User",
        department="Engineering",
        designation="Tester",
        status="Active"
    )
    db.add(emp_record)
    db.commit()

    engine = InOutEngine(in_cooldown_seconds=10.0, out_cooldown_seconds=10.0)

    # 1. Simulate Webcam / RTSP detection IN
    emp_dict = {"employee_id": test_emp_id, "name": "CCTV Test User"}
    outcome_in = engine.process_confirmed_face(
        employee=emp_dict,
        camera_id="webcam_test",
        similarity=0.88,
        screenshot_path="test_shot_in.jpg",
        source_type="webcam",
        session_id=webcam_sid,
        direction_override="IN",
        camera_name_override="Webcam Entrance"
    )
    print("1. Processed IN detection:", outcome_in)
    assert outcome_in["event_created"] and outcome_in["movement_state"] == "IN"

    # Verify DB records created
    ev_in = db.query(AttendanceEvent).filter(
        AttendanceEvent.employee_id == test_emp_id,
        AttendanceEvent.event_date == today_str,
        AttendanceEvent.event_type == "IN"
    ).first()
    assert ev_in is not None, "AttendanceEvent for IN must be saved in DB"
    assert ev_in.camera_name == "Webcam Entrance"

    # Verify AttendanceInterval created
    inv = db.query(AttendanceInterval).filter(
        AttendanceInterval.employee_id == test_emp_id,
        AttendanceInterval.date == today_str
    ).first()
    assert inv is not None and inv.in_time is not None and inv.out_time is None

    # Verify AttendanceSession (daily) created
    sess = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == test_emp_id,
        AttendanceSession.date == today_str
    ).first()
    assert sess is not None and sess.current_status == "Inside"

    # Verify legacy Attendance table synchronized
    att = db.query(Attendance).filter(
        Attendance.employee_id == test_emp_id,
        Attendance.date == today_str
    ).first()
    assert att is not None and att.status == "Present"
    print("✓ All 4 database tables (AttendanceEvent, AttendanceInterval, AttendanceSession, Attendance) verified for IN event.")

    # 2. Test Cooldown / Duplicate Suppression
    dup_outcome = engine.process_confirmed_face(
        employee=emp_dict,
        camera_id="webcam_test",
        similarity=0.89,
        screenshot_path="test_shot_in_2.jpg",
        source_type="webcam",
        session_id=webcam_sid,
        direction_override="IN",
        camera_name_override="Webcam Entrance"
    )
    print("2. Duplicate IN detection under cooldown:", dup_outcome)
    assert not dup_outcome["event_created"] and dup_outcome["reason"] in ("duplicate_state", "cooldown")

    # 3. Simulate OUT detection
    time.sleep(1.0)
    outcome_out = engine.process_confirmed_face(
        employee=emp_dict,
        camera_id="webcam_test",
        similarity=0.91,
        screenshot_path="test_shot_out.jpg",
        source_type="webcam",
        session_id=webcam_sid,
        direction_override="OUT",
        camera_name_override="Webcam Exit"
    )
    print("3. Processed OUT detection:", outcome_out)
    assert outcome_out["event_created"] and outcome_out["movement_state"] == "OUT"

    # Verify interval closed
    db.refresh(inv)
    assert inv.out_time is not None and inv.duration_seconds >= 0.0

    # Verify status changed to Completed / Outside
    db.refresh(sess)
    assert sess.current_status == "Completed"
    assert sess.total_out_events == 1

    db.close()
    print("✓ OUT event closed interval and updated daily status cleanly.")

    print("\n==============================================")
    print("ALL CCTV & LIVE PROCESSOR TESTS COMPLETED 100%! ✓")
    print("==============================================")


if __name__ == "__main__":
    run_tests()
