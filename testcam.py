import cv2

RTSP_URL = "rtsp://xtpujr:Good000$@106.203.210.45/8000/Streaming/Channels/101"

cap = cv2.VideoCapture(RTSP_URL)

print("Connected:", cap.isOpened())

if not cap.isOpened():
    print("❌ Could not open RTSP stream")
    exit()

print("✅ RTSP stream connected")

while True:
    ret, frame = cap.read()

    if not ret:
        print("❌ Failed to receive frame")
        break

    cv2.imshow("Hikvision CCTV Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
