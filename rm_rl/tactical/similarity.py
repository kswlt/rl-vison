"""Similar-state retrieval (Milestone 9).

Finds historical situations closest to a given (game, second, camp, robot).
The state signature is a *curated* low-dim vector — not a raw euclidean over
the 161-D observation — covering:

    remaining time | structure HP (both outposts + bases) | alive counts |
    own formation (centroid x/y, width, depth) | ego position / hp / yaw |
    relative vector to the enemy formation centroid

A one-off per-game matrix is cached to disk (per DB signature); each query is
then a vectorised weighted-L2 search over all cached seconds.  The response
never claims prediction — it is "these historical situations were similar and
here is what happened next".
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Dict, List, Optional

import numpy as np

from ..data import build_dataset as BD
from ..data import schema as S
from .cache import get_or_compute as _get_or_compute

FEAT_DIM = 23
DEFAULT_WEIGHTS = {
    "time": 1.0, "structure": 2.0, "alive": 2.0, "formation": 1.5,
    "ego": 1.5, "enemy": 2.0,
}


def _feat_vec(game: "BD.GameArrays", t: int, camp: str, rtype: str) -> np.ndarray:
    """One 20-D signature at second ``t`` (1-indexed)."""
    idx = int(np.clip(t, 1, game.T)) - 1
    ego = game.get(rtype, camp)
    opp = S.CAMP_BLUE if camp == S.CAMP_RED else S.CAMP_RED
    fx, fy = S.FIELD_X, S.FIELD_Y

    def e(rt, c):
        return game.get(rt, c)

    # time remaining
    rem = float(np.clip((game.T - t) / max(game.T, 1), 0.0, 1.0))
    # structure hp ratios
    op_r, op_b = e("前哨站", "红"), e("前哨站", "蓝")
    ba_r, ba_b = e("基地", "红"), e("基地", "蓝")
    struc = [op_r.hp[idx] / max(op_r.maxhp[idx], 1e-3),
             op_b.hp[idx] / max(op_b.maxhp[idx], 1e-3),
             ba_r.hp[idx] / max(ba_r.maxhp[idx], 1e-3),
             ba_b.hp[idx] / max(ba_b.maxhp[idx], 1e-3)]
    # alive counts
    alive = [0.0, 0.0]
    for c, slot in ((camp, 0), (opp, 1)):
        n = 0
        for rt in S.MOBILE_TYPES:
            ent = game.get(rt, c)
            if ent is not None and ent.alive[idx] > 0:
                n += 1
        alive[slot] = n / max(len(S.MOBILE_TYPES), 1)

    def centroid(c):
        xs, ys = [], []
        for rt in S.MOBILE_TYPES:
            ent = game.get(rt, c)
            if ent is not None and ent.alive[idx] > 0:
                xs.append(float(ent.x[idx])); ys.append(float(ent.y[idx]))
        if not xs:
            return np.array([-9.0, -9.0])
        return np.array([np.mean(xs) / fx, np.mean(ys) / fy])

    c_own, c_opp = centroid(camp), centroid(opp)
    xs = []
    for rt in S.MOBILE_TYPES:
        ent = game.get(rt, camp)
        if ent is not None and ent.alive[idx] > 0:
            xs.append(float(ent.x[idx]))
    width = (np.ptp(xs) / fx) if xs else 0.0
    ys_ = []
    for rt in S.MOBILE_TYPES:
        ent = game.get(rt, camp)
        if ent is not None and ent.alive[idx] > 0:
            ys_.append(float(ent.y[idx]))
    depth = (np.ptp(ys_) / fy) if ys_ else 0.0

    ego_x = float(ego.x[idx]) / fx if ego is not None else 0.5
    ego_y = float(ego.y[idx]) / fy if ego is not None else 0.5
    ego_hp = (float(ego.hp[idx]) / max(float(ego.maxhp[idx]), 1e-3)
              if ego is not None else 0.0)
    ego_yaw = (float(ego.yaw[idx]) / 360.0 + 0.5) if ego is not None else 0.5

    rel = c_opp - c_own
    rel_dist = float(np.hypot(rel[0], rel[1])) if c_opp[0] > -8 else 1.0

    return np.array([rem] + struc + alive +
                    [c_own[0], c_own[1], width, depth,
                     ego_x, ego_y, ego_hp, ego_yaw,
                     rel[0], rel[1], rel_dist] +
                    [0.0] * (FEAT_DIM - 18), np.float32)


def build_feature_table(db_path: str) -> Dict:
    """Precompute one signature per (game, second, camp, rtype), disk cached."""
    def compute():
        con = sqlite3.connect(db_path)
        try:
            gids = [r[0] for r in con.execute(
                f"SELECT DISTINCT game_id FROM {S.T_TIMESERIES}")]
        finally:
            con.close()
        rows = []
        games = {}
        for gid in gids:
            con = sqlite3.connect(db_path)
            try:
                game = BD.load_game_arrays(con, int(gid))
            finally:
                con.close()
            if game.T == 0:
                continue
            games[int(gid)] = int(game.T)
            for t in range(10, game.T + 1, 10):
                for camp in (S.CAMP_RED, S.CAMP_BLUE):
                    for rt in ("步兵3", "步兵4"):
                        v = _feat_vec(game, t, camp, rt)
                        rows.append((int(gid), float(t), camp, rt) +
                                    tuple(float(x) for x in v))
        return dict(games=games, n_rows=len(rows), rows=rows)

    return _get_or_compute(db_path, "similarity_feats", {}, compute,
                           ttl_s=86400.0)


def search(db_path: str, game_id: int, t: float, camp: str, rtype: str,
           top_k: int = 20, weights: Optional[Dict[str, float]] = None) -> Dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    table = build_feature_table(db_path)
    con = sqlite3.connect(db_path)
    try:
        game = BD.load_game_arrays(con, int(game_id))
    finally:
        con.close()
    if game.T == 0:
        raise ValueError(f"game {game_id} has no data")
    q = _feat_vec(game, int(t), camp, rtype)

    # weight vector in feature order: time(1) structure(4) alive(2) formation(4)
    # ego(4) enemy(3) spare(2)
    wv = np.array([w["time"]] * 1 + [w["structure"]] * 4 + [w["alive"]] * 2 +
                  [w["formation"]] * 4 + [w["ego"]] * 4 + [w["enemy"]] * 3 +
                  [0.0] * (FEAT_DIM - 18), np.float32)
    X = np.array([r[4:] for r in table["rows"]], np.float32)
    D = np.linalg.norm((X - q[None, :]) * wv[None, :], axis=1)
    order = np.argsort(D)[: max(top_k * 6, 60)]
    out = []
    for i in order:
        row = table["rows"][int(i)]
        gid, tt, cc, rt = row[0], float(row[1]), row[2], row[3]
        if gid == game_id:
            continue          # search *other* games only
        sim = float(1.0 / (1.0 + D[int(i)]))
        out.append((sim, gid, tt, cc, rt))
    out.sort(key=lambda x: -x[0])
    out = out[:top_k]

    items = []
    for sim, gid, tt, cc, rt in out:
        con = sqlite3.connect(db_path)
        try:
            g = BD.load_game_arrays(con, int(gid))
        finally:
            con.close()
        human = _human_next(g, int(tt), cc, rt, horizon=15)
        traj = _future_traj(g, int(tt), cc, rt, 20)
        items.append(dict(game_id=gid, t=tt, camp=cc, rtype=rt,
                          similarity=round(sim, 4), human_next=human,
                          trajectory=traj))
    return dict(query=dict(game_id=game_id, t=t, camp=camp, rtype=rtype),
                n_candidates=table["n_rows"],
                items=items,
                note="历史相似局面检索（加权 L2，时间/结构/存活/阵型/自身/敌队相对）；"
                     "相似≠预测，仅供参考复盘。"
                )


def _human_next(game, t: int, camp: str, rtype: str, horizon: int = 15) -> Dict:
    from ..data import features as F
    acts = F.build_action_raw(game, camp, rtype, action_mode="tactical",
                              goal_horizon=5)
    idx = int(np.clip(t, 1, game.T - 1)) - 1
    if idx < len(acts) and acts[idx] is not None:
        a = acts[idx]
        return dict(goal_dx=float(a[0]), goal_dy=float(a[1]),
                    fire=bool(a[2] > 0.5))
    return dict(goal_dx=0.0, goal_dy=0.0, fire=False)


def _future_traj(game, t: int, camp: str, rtype: str, seconds: int = 20) -> List:
    ego = game.get(rtype, camp)
    if ego is None:
        return []
    pts = []
    for dt in (10, 20):
        tt = int(np.clip(t + dt, 1, game.T))
        if ego.alive[tt - 1] > 0:
            pts.append(dict(dt=dt, x=round(float(ego.x[tt - 1]), 2),
                            y=round(float(ego.y[tt - 1]), 2)))
    return pts

