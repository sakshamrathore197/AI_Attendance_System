import time
from app.services.settings_service import SettingsService


class RecognitionState:
    DETECTING = "Detecting"
    CONFIRMING = "Confirming"
    RECOGNIZED = "Recognized"
    LOW_CONFIDENCE = "Low Confidence"
    UNKNOWN = "Unknown"


class RecognitionConfirmer:
    """
    Tracks per-employee-per-camera match streaks so that a single lucky
    (or unlucky) frame can never trigger an IN/OUT event on its own.

    An employee becomes "confirmed" (and therefore IN/OUT-eligible) only
    after MIN_CONFIRM_FRAMES consecutive frames match them on the same
    camera. A miss resets the streak — this is intentionally strict so a
    person walking through frame briefly doesn't flicker in and out of
    confirmation.
    """

    def __init__(self, min_confirm_frames: int = None, track_ttl_seconds: float = 5.0,
                 low_confidence_threshold: float = None, confirmed_threshold: float = None):
        self.min_confirm_frames = min_confirm_frames
        self.track_ttl_seconds = track_ttl_seconds
        self.low_confidence_threshold = low_confidence_threshold
        self.confirmed_threshold = confirmed_threshold

        # key = (camera_id, employee_id) -> track dict
        self._tracks = {}

    def get_min_confirm_frames(self) -> int:
        if self.min_confirm_frames is not None:
            return self.min_confirm_frames
        return SettingsService.get_int("confirmation_frame_count", 4)

    def get_threshold(self) -> float:
        if self.low_confidence_threshold is not None:
            return self.low_confidence_threshold
        return SettingsService.get_float("face_recognition_threshold", 0.60)

    def _key(self, camera_id, employee_id):
        return (camera_id, employee_id)

    def _new_track(self):
        return {
            "match_count": 0,
            "similarity_sum": 0.0,
            "best_similarity": 0.0,
            "last_recognized_time": None,
            "confirmed": False,
        }

    def _prune_stale(self, camera_id, now):
        """Drop tracks that haven't been touched recently, so a person who
        left frame doesn't keep an old streak alive if they reappear later."""
        stale_keys = [
            k for k, t in self._tracks.items()
            if k[0] == camera_id and t["last_recognized_time"] is not None
            and (now - t["last_recognized_time"]) > self.track_ttl_seconds
        ]
        for k in stale_keys:
            del self._tracks[k]

    def observe(self, camera_id: str, employee_id, similarity: float):
        """
        Feed one frame's recognition result for one detected face.

        employee_id: the matched employee's ID, or None if unmatched/unknown.
        similarity: the best cosine similarity score for this face this frame.

        Returns a dict describing this face's current recognition + movement
        eligibility state:
            {
                "state": RecognitionState.*,
                "confirmed": bool,       # eligible for IN/OUT this frame
                "match_count": int,
                "avg_similarity": float,
                "best_similarity": float,
            }
        """
        now = time.time()
        self._prune_stale(camera_id, now)

        thresh = self.get_threshold()
        min_frames = self.get_min_confirm_frames()

        if employee_id is None:
            return {
                "state": RecognitionState.UNKNOWN,
                "confirmed": False,
                "match_count": 0,
                "avg_similarity": 0.0,
                "best_similarity": 0.0,
            }

        if similarity < thresh:
            # Reset any in-progress streak for this employee on this camera —
            # a low-confidence frame breaks confirmation continuity.
            key = self._key(camera_id, employee_id)
            self._tracks.pop(key, None)
            return {
                "state": RecognitionState.LOW_CONFIDENCE,
                "confirmed": False,
                "match_count": 0,
                "avg_similarity": round(float(similarity), 4),
                "best_similarity": round(float(similarity), 4),
            }

        key = self._key(camera_id, employee_id)
        track = self._tracks.get(key) or self._new_track()

        track["match_count"] += 1
        track["similarity_sum"] += similarity
        track["best_similarity"] = max(track["best_similarity"], similarity)
        track["last_recognized_time"] = now

        avg_similarity = track["similarity_sum"] / track["match_count"]
        is_confirmed_now = track["match_count"] >= min_frames


        if is_confirmed_now and not track["confirmed"]:
            track["confirmed"] = True

        self._tracks[key] = track

        state = RecognitionState.RECOGNIZED if track["confirmed"] else RecognitionState.CONFIRMING

        return {
            "state": state,
            "confirmed": track["confirmed"],
            "match_count": track["match_count"],
            "avg_similarity": round(avg_similarity, 4),
            "best_similarity": round(track["best_similarity"], 4),
        }

    def reset(self, camera_id: str, employee_id=None):
        """Manually clear a track — e.g. after an IN/OUT event fires, so the
        same continuous presence doesn't immediately re-trigger confirmation
        logic in a way that fights with the cooldown in InOutEngine."""
        if employee_id is not None:
            self._tracks.pop(self._key(camera_id, employee_id), None)
        else:
            keys = [k for k in self._tracks if k[0] == camera_id]
            for k in keys:
                del self._tracks[k]
