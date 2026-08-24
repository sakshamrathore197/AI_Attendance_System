# Lab 3 — Central Source Registry and Browser Preview

Builds on Lab 1. Adds:
- A **live health-monitoring backend** (`health_monitor.py`) that polls
  MediaMTX's own API for real connection status, bitrate, reader count, and
  reconnect history per source.
- A **browser dashboard** (`dashboard.html`) showing all 4 sources as live
  tiles with real-time status badges — the "four live tiles + source-health
  dashboard" deliverable from Section 5 / Section 11.1 of the guide.

This still does not touch your attendance/embedding model — it only proves
the connectivity + monitoring layer.

## Prerequisite
Lab 1 must be running:
1. `mediamtx mediamtx.yml` (from Lab 1 folder)
2. `./publish_streams.sh` (from Lab 1 folder)

Both left running in their own terminals.

## What's included
```
lab3/
├── source_registry.json   # same registry as Lab 1
├── health_monitor.py      # polls MediaMTX API, writes source_status.json
├── dashboard.html          # browser dashboard reading that status file
└── README.md
```

## Step 1 — Start the health monitor
In a new terminal, from the `lab3` folder:
```bash
python3 health_monitor.py
```
You'll see a live-updating status line every 3 seconds, e.g.:
```
[2026-08-19T16:02:11] SIM-01:online(512kbps) | SIM-02:online(498kbps) | SIM-03:online(505kbps) | SIM-04:online(511kbps)
```
This also writes `source_status.json` in the same folder — that's what the
dashboard reads.

## Step 2 — Serve the dashboard folder over HTTP
Browsers block `fetch()` on local files opened via `file://`, so serve this
folder instead of double-clicking `dashboard.html`:
```bash
python3 -m http.server 8000
```
(run this from inside the `lab3` folder, in yet another terminal)

## Step 3 — Open it
```
http://localhost:8000/dashboard.html
```
You should see 4 tiles — Entrance, Exit, Reception, Parking — each with a
live WebRTC video preview and a status panel showing:
- **status** — online/offline (green/red)
- **bitrate** — live throughput in kbps
- **readers** — how many things are currently pulling this stream (VLC,
  browser tiles, your app, etc. all count separately)
- **reconnects** — how many times this source has dropped and come back
- **last online** — timestamp of last confirmed healthy connection

## Step 4 — Prove the health monitoring actually works
This is the part worth showing your team lead — the dashboard isn't just
decorative, it detects real failures:
1. With everything running, go to the `publish_streams.sh` terminal and
   press `Ctrl+C` to kill all 4 publishers.
2. Watch the dashboard — within ~3–6 seconds, all 4 tiles should flip to
   **offline** (red) and the video tiles will freeze/blank.
3. Re-run `./publish_streams.sh` — tiles should flip back to **online**
   (green) and the `reconnects` counter should increment by 1 for each
   source. This directly demonstrates the "independent status/FPS/error
   handling" requirement from Lab 1's spec, now visualized live.

This same kill/restart test is also most of what **Lab 5 (Failure and
Recovery Test)** asks for — worth noting in your report that you already
have evidence for it from this step.

## Step 5 — Wire your own app in as a "reader"
Since MediaMTX just counts readers regardless of who's connecting, when your
attendance app's `cv2.VideoCapture()` opens a stream, the dashboard's
`readers` count for that source will visibly go up by one — a nice live way
to prove your app is actually the one connecting, not just the dashboard's
own preview tile.

## Notes for your report
- All 4 sources are marked `Simulated` in `source_registry.json` — carry
  that same label into any screenshots or the compatibility matrix.
- `health_monitor.py` uses MediaMTX's REST API (`:9997/v3/paths/list`)
  rather than re-implementing OpenCV polling for every tile — this mirrors
  how Section 7.3 describes health monitoring as a separate concern from
  the AI worker's own frame reads.
