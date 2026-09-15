"""Core aggregate analytics: conditional occupancy heatmaps & shared store.

The store owns the read path into the referee SQLite database and exposes
per-game arrays with a small in-process cache (a full 613-game rescan of the
4M-row timeseries table is seconds-to-minutes, which is fine for the precompute
pipeline but not for per-request work; requests hit the precomputed cache).

``occupancy_heatmap`` is the workhorse behind the dashboard's conditional
heatmap layer: filter the whole league down to (team, rtype, phase, structure,
numbers) conditions and count where the robots stood, per 1 m grid cell.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data import schema as S
from ..data.build_dataset import load_game_arrays, load_matches
from .conditions import Condition, build_seconds, mask_seconds
from .schemas import HeatmapCell, HeatmapOut

CELL_DEFAULT = 1.0
MIN_SAMPLE = 5          # below this many (robot, second) samples we say "insufficient"


class TacticalStore:
    """Read path into the referee SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._game_cache: Dict[int, object] = {}
        self._seconds_cache: Dict[int, Dict] = {}
        self._matches: Optional[pd.DataFrame] = None

    # -- connectivity -------------------------------------------------------
    @property
    def con(self):
        return sqlite3.connect(self.db_path)

    def matches(self) -> pd.DataFrame:
        if self._matches is None:
            con = self.con
            self._matches = load_matches(con)
            con.close()
        return self._matches

    def school_team_ids(self) -> List[str]:
        return sorted(set(self.matches()["red_school"]) |
                      set(self.matches()["blue_school"]))

    def match(self, game_id: int) -> Optional[pd.Series]:
        m = self.matches()
        row = m[m.game_id == int(game_id)]
        return row.iloc[0] if not row.empty else None

    def game_ids_for_school(self, school: str, as_camp: Optional[str] = None) -> List[int]:
        """game_ids where ``school`` participated (optionally on one side)."""
        m = self.matches()
        if as_camp == S.CAMP_RED:
            sel = m[m.red_school == school]
        elif as_camp == S.CAMP_BLUE:
            sel = m[m.blue_school == school]
        else:
            sel = m[(m.red_school == school) | (m.blue_school == school)]
        return [int(g) for g in sel.game_id]

    def game(self, game_id: int):
        if game_id not in self._game_cache:
            con = self.con
            g = load_game_arrays(con, game_id)
            con.close()
            self._game_cache[game_id] = g
        return self._game_cache[game_id]

    def seconds(self, game_id: int) -> Dict[int, object]:
        if game_id not in self._seconds_cache:
            self._seconds_cache[game_id] = build_seconds(self.game(game_id))
        return self._seconds_cache[game_id]

    def camp_of(self, game_id: int, school: str) -> Optional[str]:
        m = self.match(game_id)
        if m is None:
            return None
        if m.red_school == school:
            return S.CAMP_RED
        if m.blue_school == school:
            return S.CAMP_BLUE
        return None

    def opponent_of(self, game_id: int, school: str) -> str:
        m = self.match(game_id)
        if m is None:
            return ""
        if m.red_school == school:
            return str(m.blue_school)
        if m.blue_school == school:
            return str(m.red_school)
        return ""


# ---------------------------------------------------------------------------
# Occupancy heatmap
# ---------------------------------------------------------------------------
def occupancy_heatmap(store: TacticalStore, cond: Condition,
                      cell_m: float = CELL_DEFAULT, school: str = "",
                      camp: str = "", rtype: str = "",
                      limit_games: int = 0) -> HeatmapOut:
    """Count robot-seconds per grid cell under ``cond``.

    The perspective team is either ``school`` (resolved to a camp per game) or
    a fixed ``camp``.  ``rtype`` narrows to one robot type ('' = all mobile).
    Samples are (robot, second) pairs of live, tracked robots.
    """
    t0 = time.time()
    nx = int(round(S.FIELD_X / cell_m))
    ny = int(round(S.FIELD_Y / cell_m))
    grid = np.zeros((ny, nx), np.float64)
    gids: List[int] = []

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
        any_t = False
        for t, ok in mask.items():
            if not ok:
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
                ix = int(np.clip(x // cell_m, 0, nx - 1))
                iy = int(np.clip(y // cell_m, 0, ny - 1))
                grid[iy, ix] += 1.0
                n_samples += 1
                any_t = True
        if any_t:
            n_matches += 1

    cells = []
    total = max(n_samples, 1)
    for iy in range(ny):
        for ix in range(nx):
            v = grid[iy, ix]
            if v > 0:
                cells.append(HeatmapCell(x=ix, y=iy, count=float(v),
                                         density=float(v / total)))
    cells.sort(key=lambda c: -c.count)
    note = ""
    if n_samples < MIN_SAMPLE:
        note = "样本不足"
    return HeatmapOut(
        team_id=school, rtype=rtype, phase=cond.label(),
        nx=nx, ny=ny, cell_m=cell_m,
        cells=cells, n=n_samples, n_matches=n_matches,
        reliable=n_samples >= MIN_SAMPLE, note=note,
    )
