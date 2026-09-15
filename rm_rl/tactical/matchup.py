"""Matchup analysis: two-team head-to-head from historical meetings.

Answers "上海交通大学 vs 广东工业大学": where does each team typically stand,
where do they first clash, and which areas are contested. Everything is
*historical statistics* — the API response explicitly labels first-contact
data as historical, never as a future prediction.

First contact is detected geometrically: the earliest second where a robot of
team A and a robot of team B are within CONTACT_DIST of each other, both alive
and tracked. This avoids depending on the events table's target attribution
(NULL for shots/hits).
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional

import numpy as np

from ..data import schema as S
from .analytics import TacticalStore
from .schemas import HeatmapCell, MatchupOut

CONTACT_DIST = 3.0     # metres between enemy robots to count as "contact"
CELL_DEFAULT = 1.0


def _grid_positions(game, camp: str, cell_m: float):
    """All tracked live positions of ``camp``'s mobile robots."""
    nx = int(round(S.FIELD_X / cell_m))
    ny = int(round(S.FIELD_Y / cell_m))
    grid = np.zeros((ny, nx), np.int64)
    n = 0
    # per-second robot positions
    for t in range(1, game.T + 1):
        for rid, e in game.ent.items():
            if (rid > 100) != (camp == S.CAMP_BLUE):
                continue
            rtype = _rtype_of(rid)
            if rtype in (S.TYPE_BASE, S.TYPE_OUTPOST):
                continue
            if not bool(e.alive[t - 1]):
                continue
            x, y = float(e.x[t - 1]), float(e.y[t - 1])
            if abs(x) < 1e-6 and abs(y) < 1e-6:
                continue
            ix = int(np.clip(x // cell_m, 0, nx - 1))
            iy = int(np.clip(y // cell_m, 0, ny - 1))
            grid[iy, ix] += 1
            n += 1
    return grid, n


def _first_contacts(game, camp_a: str, camp_b: str):
    """Earliest geometric contact second(s) between the two camps."""
    T = game.T
    best = None
    # iterate per second; break at first contact to keep it cheap
    for t in range(1, T + 1):
        a_pts = []
        b_pts = []
        for rid, e in game.ent.items():
            if not bool(e.alive[t - 1]):
                continue
            x, y = float(e.x[t - 1]), float(e.y[t - 1])
            if abs(x) < 1e-6 and abs(y) < 1e-6:
                continue
            camp = S.CAMP_BLUE if rid > 100 else S.CAMP_RED
            rtype = _rtype_of(rid)
            if rtype in (S.TYPE_BASE, S.TYPE_OUTPOST):
                continue
            (a_pts if camp == camp_a else b_pts).append((x, y, rid, rtype))
        for (ax, ay, arid, art) in a_pts:
            for (bx, by, brid, brt) in b_pts:
                if math.hypot(ax - bx, ay - by) < CONTACT_DIST:
                    return (float(t), (ax + bx) / 2, (ay + by) / 2,
                            art, brt, arid, brid)
    return best


def matchup(store: TacticalStore, team_a: str, team_b: str,
            cell_m: float = CELL_DEFAULT,
            limit_games: int = 0) -> MatchupOut:
    t0 = time.time()
    gids_a = set(store.game_ids_for_school(team_a))
    gids_b = set(store.game_ids_for_school(team_b))
    common = sorted(gids_a & gids_b, reverse=True)
    if limit_games > 0:
        common = common[:limit_games]

    nx = int(round(S.FIELD_X / cell_m))
    ny = int(round(S.FIELD_Y / cell_m))
    ga = np.zeros((ny, nx), np.int64)
    gb = np.zeros((ny, nx), np.int64)
    contacts: List[Dict] = []
    n_matches = 0

    for gid in common:
        camp_a = store.camp_of(gid, team_a)
        camp_b = store.camp_of(gid, team_b)
        if not camp_a or not camp_b:
            continue
        game = store.game(gid)
        if game.T == 0:
            continue
        grid_a, _ = _grid_positions(game, camp_a, cell_m)
        grid_b, _ = _grid_positions(game, camp_b, cell_m)
        ga += grid_a
        gb += grid_b
        n_matches += 1
        fc = _first_contacts(game, camp_a, camp_b)
        if fc:
            contacts.append(dict(t=fc[0], x=fc[1], y=fc[2],
                                 a_rtype=fc[3], b_rtype=fc[4],
                                 a_rid=fc[5], b_rid=fc[6]))

    def cells_of(grid) -> List[HeatmapCell]:
        out = []
        total = max(int(grid.sum()), 1)
        for iy in range(ny):
            for ix in range(nx):
                v = int(grid[iy, ix])
                if v > 0:
                    out.append(HeatmapCell(x=ix, y=iy, count=float(v),
                                           density=float(v / total)))
        out.sort(key=lambda c: -c.count)
        return out

    a_cells = cells_of(ga)
    b_cells = cells_of(gb)
    # contested cells: both teams occupy the same 1 m cell
    overlap = []
    for c in a_cells:
        if any(d.x == c.x and d.y == c.y for d in b_cells):
            overlap.append(HeatmapCell(x=c.x, y=c.y,
                                       count=min(c.count, next(
                                           d.count for d in b_cells
                                           if d.x == c.x and d.y == c.y)),
                                       density=0.0))
    overlap.sort(key=lambda c: -c.count)

    times = [c["t"] for c in contacts]
    first_contact = {
        "n": len(contacts),
        "times": times,
        "mean_t": round(float(np.mean(times)), 1) if times else None,
        "median_t": round(float(np.median(times)), 1) if times else None,
        "cells": [
            HeatmapCell(x=int(np.clip(c["x"] // cell_m, 0, nx - 1)),
                        y=int(np.clip(c["y"] // cell_m, 0, ny - 1)),
                        count=1.0, density=0.0).model_dump()
            for c in contacts
        ],
        "note": "历史统计（首次交火为双方机器人首次进入3m内）",
    }

    return MatchupOut(
        team_a=team_a, team_b=team_b, matches=[],
        first_contact=first_contact, overlap=overlap,
        a_heat=a_cells, b_heat=b_cells,
        nx=nx, ny=ny, cell_m=cell_m,
        n=len(contacts), n_matches=n_matches,
        note="历史统计，非未来预测",
    )


def _rtype_of(rid: int) -> str:
    from ..data import schema as _S
    base = rid if rid <= 100 else rid - 100
    for rtype, b in _S.RED_ID.items():
        if b == base:
            return rtype
    return "未知"
