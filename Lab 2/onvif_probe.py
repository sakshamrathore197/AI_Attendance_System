"""
Lab 2 - ONVIF Discovery and Stream Retrieval
Step 2: Probe a specific device via ONVIF.

Once you have a device IP (from onvif_discover.py, or from the camera's
label/manual/web UI), this connects to its ONVIF media service and
retrieves exactly what the guide's Section 1.1 / 7.1 onboarding flow
calls for:
    - device information (manufacturer, model, firmware)
    - media profiles (Profile S/T entries the camera supports)
    - main-stream and substream RTSP URIs, pulled from ONVIF itself
      rather than guessed from a vendor's published URL pattern

This is the "use ONVIF discovery and capability checks first" step from
Section 1.1 - it should always be tried before falling back to a vendor's
documented RTSP path.

Usage:
    python3 onvif_probe.py --ip 192.168.29.168 --port 80 --user admin --password yourpassword

If you don't have a real ONVIF camera available, see README.md for the
no-hardware ONVIF practice route (ONVIF Device Manager against a virtual
ONVIF server) - mark any such result "Simulated", never "Authorized
Hardware Tested", per Section 6.5.
"""

import argparse
import json
from datetime import datetime
from onvif import ONVIFCamera


def probe(ip, port, user, password):
    print(f"Connecting to ONVIF device at {ip}:{port} ...")
    cam = ONVIFCamera(ip, port, user, password)

    result = {"ip": ip, "port": port, "tested_at": datetime.now().isoformat(timespec="seconds")}

    # --- Device information ---
    device_service = cam.create_devicemgmt_service()
    info = device_service.GetDeviceInformation()
    result["device_info"] = {
        "manufacturer": info.Manufacturer,
        "model": info.Model,
        "firmware_version": info.FirmwareVersion,
        "serial_number": info.SerialNumber,
    }
    print("\n--- Device Information ---")
    for k, v in result["device_info"].items():
        print(f"  {k}: {v}")

    # --- Media profiles ---
    media_service = cam.create_media_service()
    profiles = media_service.GetProfiles()
    result["profiles"] = []

    print(f"\n--- Media Profiles ({len(profiles)} found) ---")
    for profile in profiles:
        entry = {"name": profile.Name, "token": profile.token}

        # Ask ONVIF for this profile's RTSP stream URI (main or sub, per profile)
        try:
            stream_setup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            uri_response = media_service.GetStreamUri(
                {"StreamSetup": stream_setup, "ProfileToken": profile.token}
            )
            entry["stream_uri"] = uri_response.Uri
        except Exception as e:
            entry["stream_uri"] = None
            entry["stream_uri_error"] = str(e)

        # Try to fetch a snapshot URI too, if supported
        try:
            snap = media_service.GetSnapshotUri({"ProfileToken": profile.token})
            entry["snapshot_uri"] = snap.Uri
        except Exception:
            entry["snapshot_uri"] = None

        result["profiles"].append(entry)
        print(f"  Profile: {entry['name']} ({entry['token']})")
        print(f"    Stream URI:   {entry.get('stream_uri')}")
        print(f"    Snapshot URI: {entry.get('snapshot_uri')}")

    out_path = f"onvif_probe_{ip.replace('.', '_')}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved full result to {out_path}")
    print("Next: test the printed Stream URI in VLC, then ffprobe, then OpenCV,")
    print("      per Section 3.1's standard onboarding sequence.")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe an ONVIF device for profiles and stream URIs")
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    probe(args.ip, args.port, args.user, args.password)
