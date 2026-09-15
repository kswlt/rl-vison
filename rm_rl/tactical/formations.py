"""Formation metrics for one team over one match.

Robots are *not* independent points: coaches care about whether the team
spreads out, pushes, or collapses.  These metrics are computed per second from
the live mobile units of one camp:

  centroid          team centre of mass (x, y)
  width             lateral spread (x-axis, canonical red frame)
  depth             longitudinal spread (y-axis)
  spacing           mean pairwise distance between robots
  front/back        which robots lead / trail (by y in canonical frame)
  area              approximate convex-hull area (or bounding-box area)
  concentration     how much of the mass sits in one spot (1 - normalised
                    mean pairwise distance)

The dashboard draws these on the tactical map (centroid + linkage) and as
time-series charts below it.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from ..data import schema as S
from .analytics import TacticalStore
from .schemas import FormationOut, FormationPoint


def formation_series(store: TacticalStore, game_id: int, camp: str,
                     step: int = 1) -> FormationOut:
    game = store.game(game_id)
    if game.T == 0:
        return FormationOut(game_id=game_id, camp=camp, points=[])
    seconds = store.seconds(game_id)
    points: List[FormationPoint] = []

    for t in range(1, game.T + 1, step):
        s = seconds[t]
        xs, ys, ids = [], [], []
        for rid, st in s.robots.items():
            if st["camp"] != camp or not st["alive"]:
                continue
            if st["rtype"] in (S.TYPE_BASE, S.TYPE_OUTPOST):
                continue
            if abs(st["x"]) < 1e-6 and abs(st["y"]) < 1e-6:
                continue
            xs.append(st["x"])
            ys.append(st["y"])
            ids.append(rid)
        if len(xs) < 1:
            continue
        xs = np.asarray(xs, np.float64)
        ys = np.asarray(ys, np.float64)
        n = len(xs)
        cx, cy = float(xs.mean()), float(ys.mean())
        width = float(np.ptp(xs)) if n > 1 else 0.0
        depth = float(np.ptp(ys)) if n > 1 else 0.0
        # mean pairwise distance (O(n^2), n <= 6 so fine)
        if n > 1:
            d = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    d += np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            spacing = 2.0 * d / (n * (n - 1))
        else:
            spacing = 0.0
        # front = largest y (canonical frame, y grows toward enemy side)
        order = np.argsort(-ys)
        front_rid, back_rid = ids[int(order[0])], ids[int(order[-1])]
        area = width * depth
        concentration = 1.0 - min(1.0, spacing / max(np.hypot(S.FIELD_X, S.FIELD_Y), 1e-6))
        points.append(FormationPoint(
            t=float(t), centroid_x=round(cx, 2), centroid_y=round(cy, 2),
            width=round(width, 2), depth=round(depth, 2),
            spacing=round(spacing, 2), front_robot=str(front_rid),
            back_robot=str(back_rid), area=round(area, 2),
            concentration=round(float(concentration), 3),
        ))
    return FormationOut(game_id=game_id, camp=camp, points=points)


def formation_stats_summary(series: FormationOut) -> Dict[str, float]:
    """Season/phase-level aggregates for opponent intelligence."""
    if not series.points:
        return {}
    w = np.array([p.width for p in series.points])
    d = np.array([p.depth for p in series.points])
    sp = np.array([p.spacing for p in series.points])
    cc = np.array([p.concentration for p in series.points])
    return dict(
        mean_width=float(w.mean()), mean_depth=float(d.mean()),
        mean_spacing=float(sp.mean()), mean_concentration=float(cc.mean()),
        push_frac=float((d > np.median(d)).mean()),
    )
