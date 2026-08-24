"""
Lab 3 - Central Source Registry and Browser Preview
Health monitor: polls MediaMTX's built-in API (port 9997) every few seconds
for the live status of every path defined in source_registry.json, and
writes a single status file the dashboard reads. This is the "source-health
dashboard" backend described in Section 7 / Section 11.1 of the guide.

Fields tracked per source (Section 7.3 style):
    - status            : "online" | "offline"
    - ready              : whether MediaMTX considers the path publishing
    - bytes_received      : cumulative bytes MediaMTX has received on this path
    - throughput_bps       : approximate live bitrate (delta since last poll)
    - reader_count          : number of active consumers (VLC, dashboard, your app, etc.)
    - reconnect_count        : how many times this source has flipped offline -> online
    - last_seen_online         : timestamp of last confirmed "ready" state
    - last_error                : most recent problem noted for this source

Usage:
    python3 health_monitor.py
Then open dashboard.html (via a local web server - see README) in a browser.
"""

import json
import time
import os
import urllib.request
from datetime import datetime

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "source_registry.json")
STATUS_PATH = os.path.join(os.path.dirname(__file__), "source_status.json")
MEDIAMTX_API = "http://localhost:9997/v3/paths/list"
POLL_INTERVAL_SEC = 3

# Persisted across polls so we can compute deltas / detect reconnects
_prev_bytes = {}
_reconnect_counts = {}
_was_ready = {}
_last_seen_online = {}


def fetch_mediamtx_paths():
    try:
        with urllib.request.urlopen(MEDIAMTX_API, timeout=2) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"[health_monitor] Could not reach MediaMTX API: {e}")
        return None


def path_name_from_uri(uri):
    # rtsp://localhost:8554/entrance -> entrance
    return uri.rstrip("/").split("/")[-1]


def build_status(registry):
    api_data = fetch_mediamtx_paths()
    api_paths = {}
    if api_data and "items" in api_data:
        for item in api_data["items"]:
            api_paths[item.get("name")] = item

    now = datetime.now().isoformat(timespec="seconds")
    status_report = {"updated_at": now, "sources": []}

    for source in registry:
        source_id = source["source_id"]
        path_name = path_name_from_uri(source["stream_uri"])
        info = api_paths.get(path_name)

        if info is None:
            status = "offline"
            ready = False
            bytes_received = 0
            reader_count = 0
            last_error = "path not found on MediaMTX (publisher not running?)"
        else:
            ready = bool(info.get("ready", False))
            bytes_received = info.get("bytesReceived", 0) or 0
            reader_count = len(info.get("readers", []))
            status = "online" if ready else "offline"
            last_error = "" if ready else "path exists but not currently publishing"

        prev = _prev_bytes.get(source_id, bytes_received)
        throughput_bps = max(0, (bytes_received - prev) * 8 / POLL_INTERVAL_SEC)
        _prev_bytes[source_id] = bytes_received

        was_ready = _was_ready.get(source_id, False)
        if ready and not was_ready:
            _reconnect_counts[source_id] = _reconnect_counts.get(source_id, 0) + (
                1 if source_id in _was_ready else 0  # don't count the very first connect
            )
        if ready:
            _last_seen_online[source_id] = now
        _was_ready[source_id] = ready

        status_report["sources"].append({
            "source_id": source_id,
            "location": source["location"],
            "direction": source["direction"],
            "brand_simulated": source["brand_simulated"],
            "stream_uri": source["stream_uri"],
            "path_name": path_name,
            "status": status,
            "ready": ready,
            "bytes_received": bytes_received,
            "throughput_bps": round(throughput_bps, 1),
            "reader_count": reader_count,
            "reconnect_count": _reconnect_counts.get(source_id, 0),
            "last_seen_online": _last_seen_online.get(source_id, "never"),
            "last_error": last_error,
        })

    return status_report


def main():
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)["sources"]

    print(f"Monitoring {len(registry)} sources every {POLL_INTERVAL_SEC}s. "
          f"Writing status to {STATUS_PATH}")
    print("Make sure mediamtx is running and publish_streams.sh is active.\n")

    while True:
        report = build_status(registry)
        with open(STATUS_PATH, "w") as f:
            json.dump(report, f, indent=2)

        line = " | ".join(
            f"{s['source_id']}:{s['status']}({s['throughput_bps']/1000:.0f}kbps)"
            for s in report["sources"]
        )
        print(f"[{report['updated_at']}] {line}")

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
