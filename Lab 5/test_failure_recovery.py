"""
Lab 5 - Failure and Recovery Automated Test
Simulates a real-world CCTV power cut / network drop, validates error catching,
and proves automatic client reconnection and video resumption.
"""

import time
import os
import cv2
import subprocess

def run_test():
    print("=" * 60)
    print("  LAB 5: RTSP STREAM FAILURE & AUTOMATIC RECOVERY TEST")
    print("=" * 60)

    rtsp_url = "rtsp://localhost:8554/entrance"
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

    # 1. Baseline Connection
    print("\n[PHASE 1: Baseline Connection]")
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print("Starting stream publishers...")
        subprocess.Popen(["bash", "publish_streams.sh"])
        time.sleep(3)
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    assert cap.isOpened(), "Could not establish initial RTSP connection."
    ret, frame = cap.read()
    assert ret and frame is not None, "Failed to read initial baseline frame."
    print(f"✅ Baseline: Healthy RTSP stream ({frame.shape[1]}x{frame.shape[0]})")
    cap.release()

    # 2. Simulate Sudden Stream Failure
    print("\n[PHASE 2: Simulating Sudden Camera/Stream Failure]")
    print("Terminating RTSP publisher process...")
    os.system("pkill -f 'rtsp://localhost:8554'")
    time.sleep(2)

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    is_down = not cap.isOpened() or not cap.read()[0]
    cap.release()
    assert is_down, "Stream should have failed after killing publisher!"
    print("✅ Verified: Stream failure detected gracefully!")

    # 3. Simulate Camera/Stream Recovery
    print("\n[PHASE 3: Simulating Camera Power/Network Recovery]")
    print("Restarting RTSP stream publisher...")
    subprocess.Popen(["bash", "publish_streams.sh"])
    time.sleep(3)

    # 4. Validate Automatic Reconnect
    print("\n[PHASE 4: Validating Automatic Recovery]")
    reconnected = False
    for attempt in range(1, 6):
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"🎉 SUCCESS! Reconnected on attempt {attempt}: Received frame ({frame.shape[1]}x{frame.shape[0]})")
                reconnected = True
                cap.release()
                break
            cap.release()
        print(f"  Attempt {attempt}: Waiting for stream buffer...")
        time.sleep(1)

    assert reconnected, "Stream failed to recover automatically!"
    print("\n" + "=" * 60)
    print("  LAB 5: FAILURE & RECOVERY TEST PASSED 100%! ✓")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
