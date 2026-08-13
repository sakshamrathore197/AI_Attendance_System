class RecognitionManager:
    def __init__(self, confirm_frames=1):
        self.tracks = {}
        self.CONFIRM_FRAMES = confirm_frames
        self.LOST_FRAMES = 10

    def update_strack(self, strack, employee, score):

        if strack.confirmed and strack.employee:
            strack.state = "RECOGNIZED"
            if score > strack.score:
                strack.score = score
            return strack

        if employee:
            strack.lost_count = 0
            if strack.employee and strack.employee["employee_id"] == employee["employee_id"]:
                strack.confirm_count += 1
            else:
                strack.employee = employee
                strack.confirm_count = 1

            if score > strack.score:
                strack.score = score

            # Identified once -> immediately confirm and lock
            if strack.confirm_count >= self.CONFIRM_FRAMES:
                strack.confirmed = True
                strack.state = "RECOGNIZED"
            else:
                strack.state = "CONFIRMING"
        else:
            # If person was already identified once on this track, NEVER move to unknown!
            if strack.confirmed and strack.employee:
                strack.state = "RECOGNIZED"
            else:
                strack.state = "UNKNOWN"

        return strack

    def update(self, track_id, employee, score):
        if track_id not in self.tracks:
            self.tracks[track_id] = {
                "employee": employee,
                "score": score,
                "confirm": 1 if employee else 0,
                "lost": 0,
                "confirmed": True if employee else False,
                "state": "RECOGNIZED" if employee else "DETECTING"
            }
            return self.tracks[track_id]

        track = self.tracks[track_id]

        if track.get("confirmed") and track.get("employee"):
            track["state"] = "RECOGNIZED"
            return track

        if employee:
            track["lost"] = 0
            if track["employee"] and track["employee"]["employee_id"] == employee["employee_id"]:
                track["confirm"] += 1
            else:
                track["employee"] = employee
                track["confirm"] = 1

            if score > track["score"]:
                track["score"] = score

            if track["confirm"] >= self.CONFIRM_FRAMES:
                track["confirmed"] = True
                track["state"] = "RECOGNIZED"
            else:
                track["state"] = "CONFIRMING"
        else:
            if not track.get("confirmed"):
                track["lost"] += 1
                if track["lost"] >= self.LOST_FRAMES:
                    track["state"] = "LOST"

        return track