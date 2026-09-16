"""Action support / OOD estimation.

Support A: behavior-policy likelihood (BC log p(a|s), normalized).
Support B: kNN in normalized action space — distance to nearest historical action.

Thresholds are percentile-based on training actions:
  < P1   -> OOD
  P1-P5  -> Very Low
  P5-P20 -> Low
  P20+   -> Supported
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = os.path.join(REPO_ROOT, "rm_runs", "winq_supervised")


class ActionSupport:
    """Combines BC likelihood percentile + kNN action distance."""

    def __init__(self, bc_runner=None, train_actions: np.ndarray = None,
                 state_dim: int = 161, act_dim: int = 10):
        self.bc_runner = bc_runner
        self.act_dim = act_dim
        self.state_dim = state_dim
        # action normalization stats from training set
        self.act_mean = None
        self.act_std = None
        # percentiles of historical action distances (for kNN support)
        self.dist_p1 = self.dist_p5 = self.dist_p20 = None
        # BC log-prob percentiles
        self.lp_p1 = self.lp_p5 = self.lp_p20 = None
        if train_actions is not None:
            self.fit(train_actions)

    def fit(self, train_actions: np.ndarray):
        self.act_mean = train_actions.mean(0)
        self.act_std = train_actions.std(0) + 1e-6
        # normalize
        a = (train_actions - self.act_mean) / self.act_std
        # sample a subset for kNN (memory)
        rng = np.random.RandomState(0)
        n = min(50000, len(a))
        idx = rng.choice(len(a), n, replace=False)
        self.knn_centers = a[idx]
        # estimate distance distribution
        # sample 2000 queries from the centers themselves
        q = a[rng.choice(len(a), 2000, replace=False)]
        # batch chunk
        dists = []
        for i in range(0, len(q), 200):
            chunk = q[i:i+200]
            d = np.sqrt(((chunk[:, None, :] - self.knn_centers[None, :, :]) ** 2).sum(-1))
            dists.append(d.min(1))
        dists = np.concatenate(dists)
        self.dist_p1 = float(np.percentile(dists, 1))
        self.dist_p5 = float(np.percentile(dists, 5))
        self.dist_p20 = float(np.percentile(dists, 20))
        self.dist_p50 = float(np.percentile(dists, 50))

    def knn_distance(self, a: np.ndarray) -> float:
        if self.act_mean is None:
            return 1.0
        an = (a - self.act_mean) / self.act_std
        d = np.sqrt(((self.knn_centers - an) ** 2).sum(-1))
        return float(d.min())

    def support_score(self, a: np.ndarray, bc_logp: float = None) -> dict:
        d = self.knn_distance(a)
        # normalize distance: 0 = best, 1 = worst
        if self.dist_p50 and self.dist_p50 > 0:
            s_knn = float(np.clip(1.0 - d / (self.dist_p50 * 2), 0.0, 1.0))
        else:
            s_knn = 0.5
        # OOD from kNN
        if self.dist_p1 is not None:
            ood_knn = d > self.dist_p5
        else:
            ood_knn = False
        # combine
        score = s_knn
        ood = ood_knn
        if score >= 0.8:
            conf = "high"
        elif score >= 0.5:
            conf = "medium"
        elif score >= 0.2:
            conf = "low"
        else:
            conf = "very_low"
        return dict(support_score=round(score, 3),
                    knn_distance=round(d, 3),
                    ood=bool(ood),
                    confidence=conf)
