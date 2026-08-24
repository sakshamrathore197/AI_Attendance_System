"""
Lab 1 - Four-Source Virtual Camera Lab
Independent connectivity + FPS + error validation for all sources
in source_registry.json. This is the "connectivity layer" test —
it does NOT run your attendance/embedding model, it only proves each
RTSP source is reachable and delivering frames reliably, per source.

Usage:
    python3 validate_sources.py

Output:
    - Live console status per source
    - compatibility_matrix.csv (Appendix B style result)
"""

import cv2
import json
import time
import threading
import csv
import os
from datetime import datetime

_default_reg = os.path.join(os.path.dirname(__file__), "source_registry.json")
_loop_reg = os.path.join(os.path.dirname(os.path.dirname(__file__)), "loop", "source_registry.json")
REGISTRY_PATH = _loop_reg if os.path.exists(_loop_reg) else _default_reg
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "compatibility_matrix.csv")
TEST_DURATION_SEC = 5  # how long to sample frames per source

# Force TCP transport - fixes most real-world RTSP frame-drop issues
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

results = {}
results_lock = threading.Lock()


def test_source(source):
    source_id = source["source_id"]
    uri = source["stream_uri"]
    label = f"{source_id} ({source['location']}, sim. {source['brand_simulated']})"

    print(f"[{source_id}] Connecting -> {uri}")
    cap = cv2.VideoCapture(uri)

    if not cap.isOpened():
        print(f"[{source_id}] FAILED - could not open stream")
        with results_lock:
            results[source_id] = {
                "status": "FAILED",
                "fps_measured": 0,
                "frames_received": 0,
                "notes": "cap.isOpened() returned False",
            }
        return

    frame_count = 0
    error_count = 0
    start = time.time()

    while time.time() - start < TEST_DURATION_SEC:
        ret, frame = cap.read()
        if ret:
            frame_count += 1
        else:
            error_count += 1

    cap.release()
    elapsed = time.time() - start
    measured_fps = frame_count / elapsed if elapsed > 0 else 0

    status = "PASS" if frame_count > 0 and error_count == 0 else (
        "PARTIAL" if frame_count > 0 else "FAILED"
    )

    print(f"[{source_id}] {status} - {frame_count} frames in {elapsed:.1f}s "
          f"(~{measured_fps:.1f} fps), {error_count} read errors")

    with results_lock:
        results[source_id] = {
            "status": status,
            "fps_measured": round(measured_fps, 1),
            "frames_received": frame_count,
            "notes": f"{error_count} read errors" if error_count else "clean",
        }


def main():
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)["sources"]

    print(f"Testing {len(registry)} sources independently, "
          f"{TEST_DURATION_SEC}s each, in parallel...\n")

    threads = [threading.Thread(target=test_source, args=(s,)) for s in registry]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Write compatibility matrix (Appendix B style)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Source ID", "Location", "Direction", "Simulated Brand",
            "Protocol", "Stream URI", "Status", "Measured FPS",
            "Frames Received", "Notes", "Test Date", "Compatibility Level"
        ])
        for s in registry:
            r = results.get(s["source_id"], {})
            writer.writerow([
                s["source_id"], s["location"], s["direction"], s["brand_simulated"],
                s["protocol"], s["stream_uri"], r.get("status", "NOT RUN"),
                r.get("fps_measured", ""), r.get("frames_received", ""),
                r.get("notes", ""), datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Simulated"  # per doc: mark virtual-lab results as Simulated,
                             # not "Authorized Hardware Tested"
            ])

    print(f"\nResults written to {OUTPUT_CSV}")
    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    print(f"Summary: {passed}/{len(registry)} sources passed cleanly")


if __name__ == "__main__":
    main()
