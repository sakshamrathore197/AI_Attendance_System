# Lab 2 — ONVIF Discovery and Stream Retrieval

Covers Section 1.1, 3.1, and 6.5 of the guide: ONVIF should be tried first
for every camera, before falling back to a vendor-specific RTSP URL
pattern. This lab practices that discovery + retrieval flow.

## What's included
```
lab2/
├── requirements.txt      # onvif-zeep, WSDiscovery, zeep
├── onvif_discover.py     # WS-Discovery scan of the local network
├── onvif_probe.py        # connect to a specific device, pull profiles + stream URIs
└── README.md
```

## Step 1 — Install dependencies
```bash
pip install -r requirements.txt --break-system-packages
```
(drop `--break-system-packages` if you're in a virtualenv)

## Step 2 — Discovery scan (run this on real hardware if available)
```bash
python3 onvif_discover.py
```
This sends a WS-Discovery multicast probe (UDP 3702) and lists whatever
ONVIF-compliant device responds — manufacturer scope, model hints, and the
service address to use for the next step.

**Important:** run this from the same physical LAN/VLAN as the camera —
per Section 4.2, multicast discovery does not reliably cross routers or a
VPN hop. If you're testing your friend's Hikvision setup again, run this
while physically on his Wi-Fi, same as before.

**Zero results is a valid, expected outcome** if there's no ONVIF device on
the network you're currently testing from — don't treat that as a bug in
the script. Move to Step 4 (no-hardware practice) if that's your situation.

## Step 3 — Probe a specific device
Once you have an IP (from discovery, or from a camera's label/manual), and
a local ONVIF/admin login (may need to be created first — Section 3.1 step
4: "create a dedicated read-only/media user"):
```bash
python3 onvif_probe.py --ip 192.168.29.168 --port 80 --user admin --password yourpassword
```
This prints:
- **Device information** — manufacturer, model, firmware, serial
- **Media profiles** — every profile the camera exposes (often one per
  resolution/bitrate combination — main stream, substream, etc.)
- **Stream URI per profile** — the RTSP URL, retrieved live from the
  camera's own ONVIF service rather than guessed from a brand pattern
- **Snapshot URI per profile**, if the camera supports it

Results are also saved to `onvif_probe_<ip>.json` for your report.

Test the printed stream URI in VLC first, then `ffprobe <uri>`, then in
your OpenCV code — per the exact sequence Section 3.1 specifies.

## Step 4 — Practicing without a real camera (Section 6.5)
If you don't have ONVIF hardware available right now, the guide names two
legitimate no-hardware options — both explicitly meant for this:

**Option A — ONVIF Device Manager (Windows)**
A free GUI tool built specifically for ONVIF discovery/profile inspection
practice: https://sourceforge.net/projects/onvifdm/
Even without a real camera to point it at, it's useful for getting familiar
with what a normal ONVIF discovery response and profile list looks like —
screenshots of the tool's UI and its documented example flows are
reasonable evidence of familiarity for a report, clearly marked as
practice/tooling familiarization rather than a live device.

**Option B — GStreamer gst-rtsp-server ONVIF components**
A more advanced, locally-controlled virtual ONVIF server, for testing your
own `onvif_probe.py` script end-to-end against something that speaks real
ONVIF, without needing physical hardware:
https://gstreamer.freedesktop.org/documentation/gst-rtsp-server/
This lets your own script run its full discovery/probe flow and get back
real (self-hosted) ONVIF responses — useful for confirming your code path
works before you ever touch a real camera.

**Either way — mark it "Simulated" in your report, never "Authorized
Hardware Tested."** Per Section 6.5: *"A virtual source must be marked
'simulated' in the report."* Save `onvif_probe.py`'s real hardware test for
whenever you get access to your friend's Hikvision setup again, or a real
office/college camera.

## What to record (Appendix B style, ONVIF-specific fields)
For each device tested (real or simulated), record:
- Manufacturer / model / firmware (from `GetDeviceInformation`)
- ONVIF profile(s) supported (Profile S / Profile T, etc.)
- Stream URI retrieved via ONVIF vs. the vendor's documented RTSP pattern
  — note whether they matched (they usually do, but ONVIF's own answer is
  authoritative if they differ)
- Snapshot URI supported: Yes/No
- Status: Research Only / Simulated / Authorized Hardware Tested /
  Production Validated
