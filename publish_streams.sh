#!/bin/bash
# Lab 1 - Four-Source Virtual Camera Lab
# Publishes each sample video into MediaMTX as a continuous looping RTSP
# stream, simulating four independent camera/brand sources.
#
# PREREQUISITE: mediamtx must already be running (see README.md, Step 2)
#
# Usage: ./publish_streams.sh
# Stop all publishers with: pkill -f "rtsp://localhost:8554"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIDEOS="$DIR/sample_videos"
HOST="localhost"
PORT="8554"

echo "Starting 4 simulated RTSP publishers..."

ffmpeg -re -stream_loop -1 -i "$VIDEOS/entrance_hikvision_sim.mp4" \
  -c copy -f rtsp "rtsp://$HOST:$PORT/entrance" -loglevel error &
echo "  [1/4] entrance  -> rtsp://$HOST:$PORT/entrance   (simulated Hikvision)"

ffmpeg -re -stream_loop -1 -i "$VIDEOS/exit_dahua_sim.mp4" \
  -c copy -f rtsp "rtsp://$HOST:$PORT/exit" -loglevel error &
echo "  [2/4] exit      -> rtsp://$HOST:$PORT/exit       (simulated Dahua)"

ffmpeg -re -stream_loop -1 -i "$VIDEOS/reception_cpplus_sim.mp4" \
  -c copy -f rtsp "rtsp://$HOST:$PORT/reception" -loglevel error &
echo "  [3/4] reception -> rtsp://$HOST:$PORT/reception  (simulated CP Plus)"

ffmpeg -re -stream_loop -1 -i "$VIDEOS/parking_uniview_sim.mp4" \
  -c copy -f rtsp "rtsp://$HOST:$PORT/parking" -loglevel error &
echo "  [4/4] parking   -> rtsp://$HOST:$PORT/parking    (simulated Uniview)"

echo ""
echo "All 4 publishers started (PIDs: $(jobs -p | tr '\n' ' '))"
echo "Test any of them in VLC: Media -> Open Network Stream -> paste a URL above"
echo "Stop everything with: pkill -f 'rtsp://localhost:8554'"
wait
