"""Win prediction dataset.

Reuses the project's existing 161-D observation pipeline (build_obs) so the
win predictor sees exactly the same features the BC policy uses.  Labels are
the per-game final outcome (win=1 / loss=0) for one side.

Splits are by **whole game_id** — never by timestep — to prevent leakage.
Team priors are already leak-safe (see team_prior.py).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from ..data import build_dataset as BD
from ..data import features as F
from ..data import schema as S
from ..data.team_prior import TeamPrior
from ..data.vis_map import VisibilityMap

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_win_labels(db_path: str) -> Dict[int, Dict[str, str]]:
    """game_id -> {"红": "win"/"loss", "蓝": ...}"""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    out: Dict[int, Dict[str, str]] = {}
    for gid, red, blue, winner in cur.execute(
            'SELECT game_id, "红方学校", "蓝方学校", "胜方" FROM matches').fetchall():
        gid = int(gid)
        out[gid] = {
            "红": "win" if winner == "红" else "loss",
            "蓝": "win" if winner == "蓝" else "loss",
        }
    con.close()
    return out


def obs_dim(agent_type: str = "步兵3") -> int:
    return F.obs_dim(agent_type)


def iter_games(db_path: str):
    """Yield (game_id, red_school, blue_school, winner, duration)."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    rows = cur.execute(
        'SELECT game_id, "红方学校", "蓝方学校", "胜方", "时长秒" FROM matches'
    ).fetchall()
    con.close()
    for r in rows:
        yield int(r[0]), r[1], r[2], r[3], int(r[4] or 0)


def game_level_split(game_ids: List[int], val_frac=0.15, test_frac=0.15,
                     seed=42) -> Tuple[List[int], List[int], List[int]]:
    """Random split by whole game_id."""
    rng = np.random.RandomState(seed)
    ids = list(game_ids)
    rng.shuffle(ids)
    n = len(ids)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)
    test = ids[:n_test]
    val = ids[n_test:n_test + n_val]
    train = ids[n_test + n_val:]
    return train, val, test


def team_held_out_split(game_meta: List[Tuple[int, str, str]],
                        test_frac=0.2, seed=42):
    """Hold out whole schools for the test set (generalisation check)."""
    rng = np.random.RandomState(seed)
    schools = sorted({s for _, r, b in game_meta for s in (r, b) if s})
    rng.shuffle(schools)
    n_test_schools = max(1, int(len(schools) * test_frac))
    test_schools = set(schools[:n_test_schools])
    train, test = [], []
    for gid, r, b in game_meta:
        if r in test_schools or b in test_schools:
            test.append(gid)
        else:
            train.append(gid)
    # simple 85/15 train/val split from the train portion
    rng.shuffle(train)
    n_val = max(1, int(len(train) * 0.18))
    return train[n_val:], train[:n_val], test, test_schools
