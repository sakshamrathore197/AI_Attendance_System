import sys
import os

sys.path.insert(0, os.path.abspath("."))

from app.services.video_service import analyze_video
from app.database import SessionLocal
from app.models import Attendance, UnknownFace, VideoSession


def run_test():
    video_path = "static/uploads/video/WhatsApp Video 2026-08-07 at 12.25.35 PM (1).mp4"
    if not os.path.exists(video_path):
        print(f"❌ Video not found at {video_path}")
        return

    print("🚀 Processing CCTV video with updated VideoService pipeline...")
    result = analyze_video(
        video_path=video_path,
        camera_name="CCTV Camera 1",
        attendance_date="2026-08-11"
    )

    print("\n==================================================")
    print("  ANALYZE_VIDEO RESULT SUMMARY")
    print("==================================================")
    print(f"Status: {result.get('status')}")
    print(f"Total Frames: {result.get('total_frames')}")
    print(f"Processed Frames: {result.get('processed_frames')}")
    print(f"Recognized Faces: {result.get('recognized_faces')}")
    print(f"Unknown Faces: {result.get('unknown_faces')}")
    print(f"Attendance Records Marked: {result.get('records_marked')}")
    print(f"Output Video URL: {result.get('output_video_url')}")

    db = SessionLocal()
    att_records = db.query(Attendance).filter(Attendance.date == "2026-08-11").all()
    print("\n📋 Marked Attendance Records for Today:")
    for a in att_records:
        print(f"  - [{a.employee_id}] {a.employee_name}: First Seen={a.first_seen}s, Last Seen={a.last_seen}s, Total Frames={a.total_frames}")

    unk_records = db.query(UnknownFace).order_by(UnknownFace.id.desc()).limit(10).all()
    print(f"\n❓ Total UnknownFace records in DB: {db.query(UnknownFace).count()}")
    db.close()

    print("\n🎉 CCTV VIDEO PROCESSING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_test()
