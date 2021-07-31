import numpy as np
import numba as nb

from .models import LABEL_MAP
from .utils.distance import cdist
from .utils.numba import apply_along_axis, normalize_vec
from .utils.rect import get_center


class ClusterFeature:
    def __init__(self, num_clusters, metric):
        self.num_clusters = num_clusters
        self.metric = metric
        self.clusters = None
        self.cluster_sizes = None
        self._next_idx = 0

    def __len__(self):
        return self._next_idx

    def __call__(self):
        return self.clusters[:self._next_idx]

    def update(self, embedding):
        if self._next_idx < self.num_clusters:
            if self.clusters is None:
                self.clusters = np.empty((self.num_clusters, len(embedding)), embedding.dtype)
                self.cluster_sizes = np.zeros(self.num_clusters, int)
            self.clusters[self._next_idx] = embedding
            self.cluster_sizes[self._next_idx] += 1
            self._next_idx += 1
        else:
            nearest_idx = self._get_nearest_cluster(self.clusters, embedding)
            self.cluster_sizes[nearest_idx] += 1
            self._seq_kmeans(self.clusters, self.cluster_sizes, embedding, nearest_idx)

    def distance(self, embeddings):
        if self.clusters is None:
            return np.full(len(embeddings), 1.0)
        return self._nearest_cluster_dist(self.clusters[:self._next_idx], embeddings, self.metric)

    def merge(self, features, other, other_features):
        if len(features) > len(other_features):
            for feature in other_features:
                if feature is not None:
                    self.update(feature)
        else:
            for feature in features:
                if feature is not None:
                    other.update(feature)
            self.clusters = other.clusters.copy()
            self.clusters_sizes = other.cluster_sizes.copy()
            self._next_idx = other._next_idx

    @staticmethod
    @nb.njit(fastmath=True, cache=True)
    def _get_nearest_cluster(clusters, embedding):
        return np.argmin(cdist(np.atleast_2d(embedding), clusters, 'cosine'))

    @staticmethod
    @nb.njit(cache=True)
    def _nearest_cluster_dist(clusters, embeddings, metric):
        clusters = normalize_vec(clusters)
        return apply_along_axis(np.min, cdist(clusters, embeddings, metric), axis=0)

    @staticmethod
    @nb.njit(fastmath=True, cache=True)
    def _seq_kmeans(clusters, cluster_sizes, embedding, idx):
        div_size = 1. / cluster_sizes[idx]
        clusters[idx] += (embedding - clusters[idx]) * div_size


class SmoothFeature:
    def __init__(self, learning_rate):
        self.lr = learning_rate
        self.smooth = None

    def __call__(self):
        return self.smooth

    def update(self, embedding):
        if self.smooth is None:
            self.smooth = embedding.copy()
        else:
            self._rolling(self.smooth, embedding, self.lr)

    @staticmethod
    @nb.njit(fastmath=True, cache=True)
    def _rolling(smooth, embedding, lr):
        smooth[:] = (1. - lr) * smooth + lr * embedding
        norm_factor = 1. / np.linalg.norm(smooth)
        smooth *= norm_factor


class AverageFeature:
    def __init__(self):
        self.sum = None
        self.avg = None
        self.count = 0

    def __call__(self):
        return self.avg

    def update(self, embedding):
        self.count += 1
        if self.avg is None:
            self.sum = embedding.copy()
            self.avg = embedding.copy()
        else:
            self._average(self.sum, self.avg, embedding, self.count)

    def merge(self, other):
        self.count += other.count
        if self.avg is None:
            self.sum = other.sum
            self.avg = other.avg
        elif self.count > 0:
            self._average(self.sum, self.avg, other.sum, self.count)

    @staticmethod
    @nb.njit(fastmath=True, cache=True)
    def _average(sum, avg, vec, count):
        sum += vec
        div_cnt = 1. / count
        avg[:] = sum * div_cnt
        norm_factor = 1. / np.linalg.norm(avg)
        avg *= norm_factor


class Track:
    _count = 0

    def __init__(self, frame_id, tlbr, state, label, metric,
                 confirm_hits=1, num_clusters=5, learning_rate=0.1):
        self.trk_id = self.next_id()
        self.start_frame = frame_id
        self.frame_id = frame_id
        self.confirm_hits = confirm_hits
        self.tlbr = tlbr
        self.state = state
        self.label = label

        self.age = 0
        self.hits = 0
        self.clust_feat = ClusterFeature(num_clusters, metric)
        # self.smooth_feat = SmoothFeature(learning_rate)
        self.avg_feat = AverageFeature()
        self.last_feat = None

        self.inlier_ratio = 1.
        self.keypoints = np.empty((0, 2), np.float32)
        self.prev_keypoints = np.empty((0, 2), np.float32)

    def __str__(self):
        coord = get_center(self.tlbr).astype(int)
        return f'{LABEL_MAP[self.label]} {self.trk_id:>3} at ({coord[0]:>4}, {coord[1]:>3})'

    def __repr__(self):
        return self.__str__()

    def __lt__(self, other):
        # ordered by approximate distance to the image plane, closer is greater
        return (self.tlbr[-1], -self.age) < (other.tlbr[-1], -other.age)

    @property
    def end_frame(self):
        return self.frame_id

    @property
    def active(self):
        return self.age < 2

    @property
    def confirmed(self):
        return self.hits >= self.confirm_hits

    def just_confirmed(self):
        return self.hits == self.confirm_hits

    def update_location(self, tlbr, state):
        self.tlbr = tlbr
        self.state = state

    def add_detection(self, frame_id, tlbr, state, embedding, is_valid=True):
        self.frame_id = frame_id
        self.update_location(tlbr, state)
        self.update_features(embedding, is_valid)
        self.age = 0
        self.hits += 1

    def reinstate(self, frame_id, tlbr, state, embedding):
        self.frame_id = frame_id
        self.update_location(tlbr, state)
        self.update_features(embedding)
        self.age = 0
        self.keypoints = np.empty((0, 2), np.float32)
        self.prev_keypoints = np.empty((0, 2), np.float32)

    def mark_missed(self):
        self.age += 1

    def merge_continuation(self, other):
        print(self.start_frame, other.start_frame)
        print(self.end_frame, other.end_frame)
        assert self.end_frame < other.start_frame

        self.frame_id = other.frame_id
        self.update_location(other.tlbr, other.state)
        self.age = other.age
        self.hits += other.hits

        self.keypoints = other.keypoints
        self.prev_keypoints = other.prev_keypoints

        self.last_feat = other.last_feat
        self.avg_feat.merge(other.avg_feat)
        # self.clust_feat.merge(self.features, other.clust_feat, other.features)

    def update_features(self, embedding, is_valid=True):
        self.last_feat = embedding
        if is_valid:
            self.avg_feat.update(embedding)
            self.clust_feat.update(embedding)

    @staticmethod
    def next_id():
        Track._count += 1
        return Track._count
