import os
import time
from datetime import datetime

from app.storage import init_db
from app.database import SessionLocal
from app.models import Camera, SystemSetting, AttendanceEvent, AttendanceInterval, AttendanceSession, UnknownFace
from app.services.settings_service import SettingsService
from app.services.camera_manager import CameraManager
from app.services.recognition_confirmer import RecognitionConfirmer, RecognitionState
from app.services.inout_engine import InOutEngine


def run_tests():
    print("=== TEST 1: Database Initialization & Seeding ===")
    init_db()
    db = SessionLocal()
    try:
        cams = db.query(Camera).all()
        print(f"✓ Cameras initialized in DB: {len(cams)}")
        settings = db.query(SystemSetting).all()
        print(f"✓ Settings initialized in DB: {len(settings)}")
    finally:
        db.close()

    print("\n=== TEST 2: Settings Service ===")
    thresh = SettingsService.get_float("face_recognition_threshold", 0.60)
    streak = SettingsService.get_int("confirmation_frame_count", 4)
    cooldown = SettingsService.get_float("cooldown_duration", 45.0)
    print(f"✓ Initial Settings: thresh={thresh}, streak={streak}, cooldown={cooldown}s")

    SettingsService.set("cooldown_duration", "30")
    new_cooldown = SettingsService.get_float("cooldown_duration")
    assert new_cooldown == 30.0, f"Expected 30.0, got {new_cooldown}"
    print("✓ Setting update verified successfully.")

    print("\n=== TEST 3: Camera Manager CRUD & Test Connection ===")
    test_cam_data = {
        "camera_id": "test_cam_in_99",
        "camera_name": "Test Entry Gate",
        "camera_type": "webcam",
        "url_or_index": "0",
        "location": "North Entrance",
        "direction": "IN"
    }
    res = CameraManager.create_camera(test_cam_data)
    print("✓ Create camera response:", res)

    all_cams = CameraManager.get_all_cameras()
    cam_found = any(c["camera_id"] == "test_cam_in_99" for c in all_cams)
    assert cam_found, "Camera test_cam_in_99 not found in camera manager list"
    print("✓ Camera manager listing verified.")

    # Test connection to invalid RTSP URL
    rtsp_res = CameraManager.test_connection("rtsp", "rtsp://invalid.ip:554/live")
    print("✓ RTSP invalid connection test response:", rtsp_res["message"])
    assert not rtsp_res["status"], "RTSP test on invalid URL should return false status"

    print("\n=== TEST 4: Recognition Confirmer Streak & Low Confidence ===")
    confirmer = RecognitionConfirmer(min_confirm_frames=3, low_confidence_threshold=0.60)
    camera_id = "test_cam_in_99"
    emp_id = "EMP-TEST-01"

    # Frame 1
    c1 = confirmer.observe(camera_id, emp_id, 0.75)
    print("Frame 1:", c1)
    assert c1["state"] == RecognitionState.CONFIRMING and not c1["confirmed"]

    # Frame 2
    c2 = confirmer.observe(camera_id, emp_id, 0.72)
    print("Frame 2:", c2)
    assert c2["state"] == RecognitionState.CONFIRMING and not c2["confirmed"]

    # Frame 3 -> Should confirm
    c3 = confirmer.observe(camera_id, emp_id, 0.78)
    print("Frame 3 (Confirmed):", c3)
    assert c3["state"] == RecognitionState.RECOGNIZED and c3["confirmed"]

    # Low confidence frame resets track
    c_low = confirmer.observe(camera_id, emp_id, 0.45)
    print("Frame 4 (Low confidence):", c_low)
    assert c_low["state"] == RecognitionState.LOW_CONFIDENCE and not c_low["confirmed"]

    print("\n=== TEST 5: InOutEngine Sequence Validation, Intervals & Cooldown ===")
    engine = InOutEngine(in_cooldown_seconds=10.0, out_cooldown_seconds=10.0)

    # Setup 2 cameras: Camera A (IN) and Camera B (OUT)
    CameraManager.create_camera({
        "camera_id": "cam_a_in",
        "camera_name": "Gate A (IN)",
        "camera_type": "webcam",
        "url_or_index": "0",
        "direction": "IN",
        "location": "Gate A"
    })
    CameraManager.create_camera({
        "camera_id": "cam_b_out",
        "camera_name": "Gate B (OUT)",
        "camera_type": "webcam",
        "url_or_index": "1",
        "direction": "OUT",
        "location": "Gate B"
    })

    test_emp_id = f"EMP-TEST-{int(time.time())}"
    emp = {"employee_id": test_emp_id, "name": "Alice Smith"}


    # 1st Valid IN event on Camera A
    e1 = engine.process_confirmed_face(emp, "cam_a_in", 0.85)
    print("1. First IN Event:", e1)
    assert e1["event_created"] and e1["movement_state"] == "IN"

    # Cooldown suppression test on Camera A
    e2 = engine.process_confirmed_face(emp, "cam_a_in", 0.82)
    print("2. Immediate 2nd IN (Duplicate/Cooldown):", e2)
    assert not e2["event_created"] and e2["reason"] in ("duplicate_state", "cooldown")

    # Check currently inside list
    inside_list = engine.get_currently_inside()
    print("3. Currently Inside List:", inside_list)
    assert any(i["employee_id"] == test_emp_id for i in inside_list)


    # Valid OUT event on Camera B
    time.sleep(1.0)
    e3 = engine.process_confirmed_face(emp, "cam_b_out", 0.88)
    print("4. First OUT Event:", e3)
    assert e3["event_created"] and e3["movement_state"] == "OUT"

    # Verify interval 1 closed
    db = SessionLocal()
    today = datetime.now().strftime("%Y-%m-%d")
    intervals_1 = db.query(AttendanceInterval).filter(
        AttendanceInterval.employee_id == test_emp_id,
        AttendanceInterval.date == today
    ).all()
    print(f"5. Intervals after 1st OUT: {len(intervals_1)}, Duration: {intervals_1[0].duration_seconds}s")
    assert len(intervals_1) == 1 and intervals_1[0].out_time is not None
    db.close()

    # Unexpected OUT event test when already outside
    e4 = engine.process_confirmed_face(emp, "cam_b_out", 0.84)
    print("6. Duplicate OUT when outside (Unexpected):", e4)
    assert not e4["event_created"] and e4["reason"] == "unexpected"

    # 2nd IN event on Camera A (Second interval on same day)
    time.sleep(1.0)
    engine._last_event_time.clear()  # reset cooldown for testing
    e5 = engine.process_confirmed_face(emp, "cam_a_in", 0.86)
    print("7. Second IN Event (2nd interval):", e5)
    assert e5["event_created"] and e5["movement_state"] == "IN"

    # 2nd OUT event on Camera B
    time.sleep(1.0)
    engine._last_event_time.clear()
    e6 = engine.process_confirmed_face(emp, "cam_b_out", 0.89)
    print("8. Second OUT Event (2nd interval close):", e6)
    assert e6["event_created"] and e6["movement_state"] == "OUT"

    # Verify daily session total working duration equals sum of BOTH intervals!
    db = SessionLocal()
    session_row = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == test_emp_id,
        AttendanceSession.date == today
    ).first()
    intervals_2 = db.query(AttendanceInterval).filter(
        AttendanceInterval.employee_id == test_emp_id,
        AttendanceInterval.date == today
    ).all()

    total_interval_seconds = sum(i.duration_seconds for i in intervals_2)
    print(f"9. Total Intervals: {len(intervals_2)}, Sum of Interval Durations: {total_interval_seconds}s, Daily Session Total: {session_row.total_working_seconds}s")
    assert len(intervals_2) == 2, f"Expected 2 intervals, got {len(intervals_2)}"
    assert session_row.total_working_seconds == total_interval_seconds, "Daily session total working seconds must equal sum of intervals!"
    db.close()


    print("\n==========================================")
    print("ALL MANDATORY TESTS PASSED SUCCESSFULLY! ✓")
    print("==========================================")


if __name__ == "__main__":
    run_tests()
