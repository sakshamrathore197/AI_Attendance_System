import math
import numpy as np
from scipy.optimize import linear_sum_assignment


def bbox_iou(box1, box2):
    
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class KalmanFilter:
    
    def __init__(self):
        self._motion_mat = np.eye(8, 8)
        for i in range(4):
            self._motion_mat[i, i + 4] = 1.0
        self._update_mat = np.eye(4, 8)

    def initiate(self, measurement):
        mean_pos = measurement
        mean_vel = np.zeros(4)
        mean = np.r_[mean_pos, mean_vel]

        std = [
            2 * 1.0 * measurement[3],
            2 * 1.0 * measurement[3],
            1e-2,
            2 * 1.0 * measurement[3],
            10 * 1.0 * measurement[3],
            10 * 1.0 * measurement[3],
            1e-5,
            10 * 1.0 * measurement[3]
        ]
        covariance = np.diag(np.square(std))
        return mean, covariance

    def predict(self, mean, covariance):
        h = max(1e-2, mean[3])
        std_pos = [1.0 * h, 1.0 * h, 1e-2, 1.0 * h]
        std_vel = [1e-1 * h, 1e-1 * h, 1e-5, 1e-1 * h]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

        mean = np.dot(self._motion_mat, mean)
        covariance = np.linalg.multi_dot([self._motion_mat, covariance, self._motion_mat.T]) + motion_cov
        return mean, covariance

    def update(self, mean, covariance, measurement):
        projected_mean = np.dot(self._update_mat, mean)
        h = max(1e-2, mean[3])
        std = [1.0 * h, 1.0 * h, 1e-1, 1.0 * h]
        innovation_cov = np.diag(np.square(std))

        projected_cov = np.linalg.multi_dot([self._update_mat, covariance, self._update_mat.T]) + innovation_cov
        kalman_gain = np.linalg.multi_dot([covariance, self._update_mat.T, np.linalg.inv(projected_cov)])

        innovation = measurement - projected_mean
        new_mean = mean + np.dot(kalman_gain, innovation)
        new_covariance = covariance - np.linalg.multi_dot([kalman_gain, projected_cov, kalman_gain.T])
        return new_mean, new_covariance


class STrack:
    def __init__(self, bbox, det_score=1.0, embedding=None, face_obj=None):
        self.track_id = 0
        self.bbox = [float(b) for b in bbox]  # [x1, y1, x2, y2]
        self.det_score = float(det_score)
        self.embedding = embedding
        self.face_obj = face_obj

        self.state = "Tracked"
        self.lost_count = 0
        self.frame_count = 1

        # Recognition & Unknown tracking metadata
        self.employee = None
        self.score = 0.0
        self.confirm_count = 0
        self.confirmed = False

        self.unknown_db_id = None
        self.best_quality = 0.0
        self.unknown_crop_filename = None

        # Kalman state
        self.kalman_filter = KalmanFilter()
        self.mean, self.covariance = self.kalman_filter.initiate(self.to_xyah(self.bbox))

    @staticmethod
    def to_xyah(bbox):
        x1, y1, x2, y2 = bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        cx = x1 + w / 2.0
        cy = y1 + h / 2.0
        a = w / h
        return np.array([cx, cy, a, h], dtype=np.float32)

    def to_bbox(self):
        if self.mean is None:
            return self.bbox
        cx, cy, a, h = self.mean[:4]
        w = a * h
        x1 = cx - w / 2.0
        y1 = cy - h / 2.0
        x2 = cx + w / 2.0
        y2 = cy + h / 2.0
        return [float(x1), float(y1), float(x2), float(y2)]

    def predict(self):
        if self.state != "Tracked":
            self.mean[7] = 0
        self.mean, self.covariance = self.kalman_filter.predict(self.mean, self.covariance)
        self.bbox = self.to_bbox()

    def update(self, new_strack, frame_id=0):
        self.frame_count += 1
        self.bbox = [float(b) for b in new_strack.bbox]
        self.det_score = new_strack.det_score
        if new_strack.embedding is not None:
            self.embedding = new_strack.embedding
        if new_strack.face_obj is not None:
            self.face_obj = new_strack.face_obj

        self.mean, self.covariance = self.kalman_filter.update(
            self.mean, self.covariance, self.to_xyah(self.bbox)
        )
        self.state = "Tracked"
        self.lost_count = 0


class ByteTracker:
    
    def __init__(self, det_thresh=0.45, low_thresh=0.1, match_thresh=0.8, max_lost=30):
        self.det_thresh = det_thresh
        self.low_thresh = low_thresh
        self.match_thresh = match_thresh  # Max IoU distance (1.0 - IoU) for matching (0.8 cost => 0.2 IoU)
        self.max_lost = max_lost

        self.tracked_stracks = []  # active tracks
        self.lost_stracks = []     # lost tracks
        self.next_id = 1

    def update(self, faces):
        
        detections_high = []
        detections_low = []

        for face in faces:
            if hasattr(face, "bbox"):
                bbox = face.bbox.astype(float)
                det_score = float(getattr(face, "det_score", 1.0))
                embedding = getattr(face, "embedding", None)
                face_obj = face
            else:
                bbox = [float(b) for b in face["bbox"]]
                det_score = float(face.get("det_score", 1.0))
                embedding = face.get("embedding", None)
                face_obj = face

            strack = STrack(bbox, det_score, embedding, face_obj)
            if det_score >= self.det_thresh:
                detections_high.append(strack)
            elif det_score >= self.low_thresh:
                detections_low.append(strack)

        # 1. Predict track positions
        all_tracks = self.tracked_stracks + self.lost_stracks
        for track in all_tracks:
            track.predict()

        # 2. Stage 1: Associate high confidence detections with active & lost tracks
        unmatched_tracks_1, unmatched_high_dets, matched_pairs_1 = self._associate(
            all_tracks, detections_high, self.match_thresh
        )

        for track_idx, det_idx in matched_pairs_1:
            track = all_tracks[track_idx]
            det = detections_high[det_idx]
            track.update(det)
            if track in self.lost_stracks:
                self.lost_stracks.remove(track)
                self.tracked_stracks.append(track)

        # 3. Stage 2: Associate remaining unmatched tracked tracks with low confidence detections
        unmatched_tracked_from_stage_1 = [t for t in unmatched_tracks_1 if t in self.tracked_stracks]
        unmatched_tracks_2, unmatched_low_dets, matched_pairs_2 = self._associate(
            unmatched_tracked_from_stage_1, detections_low, self.match_thresh
        )

        for track in unmatched_tracked_from_stage_1:
            if track not in unmatched_tracks_2:
                # Matched with low score detection
                for t_idx, d_idx in matched_pairs_2:
                    if unmatched_tracked_from_stage_1[t_idx] == track:
                        det = detections_low[d_idx]
                        track.update(det)
                        break

        # 4. Handle unmatched tracks (move to lost or remove)
        for track in unmatched_tracks_2:
            if track in self.tracked_stracks:
                self.tracked_stracks.remove(track)
                self.lost_stracks.append(track)

        for track in self.lost_stracks[:]:
            track.lost_count += 1
            if track.lost_count > self.max_lost:
                track.state = "Removed"
                self.lost_stracks.remove(track)

        # 5. Spawn new tracks for unmatched high confidence detections
        for det_idx in unmatched_high_dets:
            det = detections_high[det_idx]
            det.track_id = self.next_id
            self.next_id += 1
            det.state = "Tracked"
            self.tracked_stracks.append(det)

        return self.tracked_stracks

    def _associate(self, tracks, detections, max_distance=0.8):
        if len(tracks) == 0 or len(detections) == 0:
            return tracks, list(range(len(detections))), []

        cost_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
        for i, t in enumerate(tracks):
            t_box = t.bbox
            for j, d in enumerate(detections):
                d_box = d.bbox
                iou = bbox_iou(t_box, d_box)
                cost_matrix[i, j] = 1.0 - iou

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matched_pairs = []
        unmatched_tracks = list(tracks)
        unmatched_dets = list(range(len(detections)))

        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] <= max_distance:
                matched_pairs.append((r, c))
                if tracks[r] in unmatched_tracks:
                    unmatched_tracks.remove(tracks[r])
                if c in unmatched_dets:
                    unmatched_dets.remove(c)

        return unmatched_tracks, unmatched_dets, matched_pairs


class TrackManager:
    def __init__(self):
        self.tracker = ByteTracker()
        self.tracks = {}

    def get_track_id(self, bbox):
        fake_face = {"bbox": bbox, "det_score": 0.9}
        active_tracks = self.tracker.update([fake_face])
        if active_tracks:
            return active_tracks[0].track_id
        return 1

    def update_tracks(self, faces):
        return self.tracker.update(faces)

    def cleanup(self):
        pass