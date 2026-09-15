"""Movement flow field: where a team/robot *goes* under a condition.

The occupancy heatmap answers "where do they stand"; the flow field answers
"from where to where".  Each cell aggregates the movement vectors of robots
that passed through it, so the dashboard can draw arrows whose direction is the
average motion and whose length encodes average speed, with opacity by sample
count.  Clicking a cell exposes enter/leave directions, stay time and the most
common next cell.
"""
from __future__ import annotations

import time
from typing import Dict, List

import numpy as np

from ..data import schema as S
from .analytics import TacticalStore
from .conditions import Condition, mask_seconds
from .schemas import FlowCell, FlowOut

CELL_DEFAULT = 2.0
MIN_SAMPLE = 3


def _cell_xy(x, y, cell_m, nx, ny):
    return (int(np.clip(x // cell_m, 0, nx - 1)),
            int(np.clip(y // cell_m, 0, ny - 1)))


def flow_field(store: TacticalStore, cond: Condition,
               cell_m: float = CELL_DEFAULT, school: str = "",
               camp: str = "", rtype: str = "",
               limit_games: int = 0) -> FlowOut:
    t0 = time.time()
    nx = int(round(S.FIELD_X / cell_m))
    ny = int(round(S.FIELD_Y / cell_m))
    n_cells = nx * ny
    # per-cell accumulators
    dx = np.zeros(n_cells, np.float64)
    dy = np.zeros(n_cells, np.float64)
    cnt = np.zeros(n_cells, np.int64)
    enter_dir = np.zeros(n_cells, np.float64)   # accumulated entering bearings
    leave_dir = np.zeros(n_cells, np.float64)   # accumulated leaving bearings
    stay = np.zeros(n_cells, np.float64)
    stay_n = np.zeros(n_cells, np.int64)
    next_cell = np.zeros((n_cells, n_cells), np.int64)  # transition counts

    if school:
        gids = store.game_ids_for_school(school)
    else:
        gids = [int(g) for g in store.matches().game_id]
    if limit_games > 0:
        gids = gids[:limit_games]

    n_samples = 0
    n_matches = 0
    for gid in gids:
        game = store.game(gid)
        if game.T == 0:
            continue
        game_camp = camp
        if school:
            game_camp = store.camp_of(gid, school) or ""
            if not game_camp:
                continue
        c = Condition(**{**cond.__dict__})
        c.camp = game_camp
        c.rtype = rtype or cond.rtype
        seconds = store.seconds(gid)
        mask = mask_seconds(c, game, seconds)

        # collect per-robot trajectories of (t, cell)
        tracks: Dict[int, List] = {}
        for t in sorted(mask.keys()):
            if not mask[t]:
                continue
            s = seconds[t]
            for rid, st in s.robots.items():
                if st["camp"] != game_camp:
                    continue
                if c.rtype and st["rtype"] != c.rtype:
                    continue
                if not st["alive"]:
                    continue
                x, y = st["x"], st["y"]
                if abs(x) < 1e-6 and abs(y) < 1e-6:
                    continue
                cell = _cell_xy(x, y, cell_m, nx, ny)
                tracks.setdefault(rid, []).append((t, cell, st))
        if tracks:
            n_matches += 1
        for rid, tr in tracks.items():
            # consecutive seconds within the same cell accumulate stay time
            prev_cell = None
            prev_t = None
            entry = None
            for k, (t, cell, st) in enumerate(tr):
                idx = cell[1] * nx + cell[0]
                cnt[idx] += 1
                n_samples += 1
                if k + 1 < len(tr):
                    nxt = tr[k + 1][1]
                    nxt_idx = nxt[1] * nx + nxt[0]
                    if nxt != cell:
                        dx[idx] += (nxt[0] - cell[0]) * cell_m
                        dy[idx] += (nxt[1] - cell[1]) * cell_m
                        next_cell[idx, nxt_idx] += 1
                # stay time: how many consecutive seconds in this cell
                if prev_cell == cell:
                    stay[idx] += 1.0
                    stay_n[idx] += 1
                else:
                    if prev_cell is not None:
                        pidx = prev_cell[1] * nx + prev_cell[0]
                        leave_dir[pidx] += _angle_deg(cell, prev_cell)
                    enter_dir[idx] += _angle_deg(cell, prev_cell) if prev_cell is not None else 0.0
                prev_cell = cell
                prev_t = t

    cells = []
    for iy in range(ny):
        for ix in range(nx):
            idx = iy * nx + ix
            if cnt[idx] == 0:
                continue
            n = cnt[idx]
            mdx = dx[idx] / max(n, 1)
            mdy = dy[idx] / max(n, 1)
            nxts = np.argsort(-next_cell[idx])[:3]
            common_next = [int(i) for i in nxts if next_cell[idx, i] > 0]
            cells.append(FlowCell(
                x=ix, y=iy,
                mean_dx=round(float(mdx), 3), mean_dy=round(float(mdy), 3),
                speed=round(float(np.hypot(mdx, mdy)), 3), n=int(n),
                enter_dir=round(float(enter_dir[idx]) / n, 2) if n else 0.0,
                leave_dir=round(float(leave_dir[idx]) / n, 2) if n else 0.0,
                stay_time=round(float(stay[idx]) / max(stay_n[idx], 1), 2),
                common_next=common_next,
            ))
    return FlowOut(team_id=school, rtype=rtype, phase=cond.label(),
                   nx=nx, ny=ny, cell_m=cell_m, cells=cells,
                   n=n_samples, n_matches=n_matches)


def _angle_deg(a, b):
    return float(np.degrees(np.arctan2(a[1] - b[1], a[0] - b[0])))
