"""Event-triggered behaviour analysis.

"What does a team generally do in the N seconds after event X?"  This module
detects tactical trigger events from the per-second state (outpost HP
thresholds, base hits, robot deaths, numbers swings, final phases) and then
classifies the responding robot's motion over the following ``horizon``
seconds into 回防 / 保持 / 前压 (fall back / hold / push).

Classification is geometric, in the *raw* field frame of the game (no
canonical mirroring): "push" means moving toward the enemy side of the arena,
"fall back" means moving toward the team's own side.  Because the referee
origin is fixed (red near y=0 … blue near y=15) we decide per camp which
direction counts as forward.

Every returned behaviour carries n (samples) and n_matches so the UI can show
statistical confidence and the underlying real cases (game_id, t, opponent).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..data import schema as S
from .analytics import TacticalStore
from .schemas import BehaviorCase, EventBehaviorOut

HORIZON_DEFAULT = 15
MOVE_EPS = 0.5          # metres of displacement that count as "moving"
MIN_SAMPLE = 5


@dataclass
class TriggerEvent:
    kind: str
    game_id: int
    t: float
    camp: str
    robot_id: int = 0
    rtype: str = ""


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------
def detect_events(store: TacticalStore, game_id: int,
                  kinds: Optional[List[str]] = None) -> List[TriggerEvent]:
    """Scan one game for trigger events (first occurrences only, per kind)."""
    game = store.game(game_id)
    if game.T == 0:
        return []
    seconds = store.seconds(game_id)
    out: List[TriggerEvent] = []
    seen: set = set()
    for camp in S.CAMPS:
        for kind, t in _first_triggers(game, seconds, camp):
            if kinds and kind not in kinds:
                continue
            key = (camp, kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(TriggerEvent(kind=kind, game_id=game_id, t=t,
                                    camp=camp))
    return out


def _first_triggers(game, seconds, camp: str) -> List[Tuple[str, float]]:
    T = game.T
    ecamp = S.enemy_camp(camp)
    res: List[Tuple[str, float]] = []
    prev_hp = None
    prev_alive = None
    prev_own = prev_opp = 0
    for t in range(1, T + 1):
        s = seconds[t]
        hp = s.outpost_hp.get(camp, 0.0)
        mx = s.outpost_max.get(camp, 1.0) or 1.0
        frac = hp / mx if mx > 0 else 0.0
        if prev_hp is not None:
            for thr, name in ((0.75, "outpost_lt75"), (0.5, "outpost_lt50"),
                              (0.25, "outpost_lt25")):
                if prev_hp / max(prev_mx, 1e-9) >= thr and frac < thr:
                    res.append((name, float(t)))
            if prev_hp > 0.0 and hp <= 0.0:
                res.append(("outpost_destroyed", float(t)))
        if s.base_hit.get(camp, False):
            res.append(("base_hit", float(t)))
        own, opp = s.alive.get(camp, 0), s.alive.get(ecamp, 0)
        if prev_own is not None and own < prev_own:
            res.append(("own_robot_down", float(t)))
        if prev_opp is not None and opp < prev_opp:
            res.append(("enemy_robot_down", float(t)))
        if prev_own is not None and prev_opp is not None:
            if prev_own <= prev_opp and own > opp:
                res.append(("numbers_advantage", float(t)))
            if prev_own >= prev_opp and own < opp:
                res.append(("numbers_disadvantage", float(t)))
        prev_hp, prev_mx = hp, mx
        prev_own, prev_opp = own, opp
    return res


# ---------------------------------------------------------------------------
# Behaviour classification
# ---------------------------------------------------------------------------
def _forward_dir(camp: str) -> float:
    """+1 if y grows toward the enemy for ``camp``, else -1."""
    return -1.0 if camp == S.CAMP_RED else 1.0


def classify_motion(x0, y0, x1, y1, camp: str) -> str:
    """回防 / 保持 / 前压 for a robot moving from (x0,y0) to (x1,y1)."""
    dx = x1 - x0
    dy = y1 - y0
    dist = float(np.hypot(dx, dy))
    if dist < MOVE_EPS:
        return "保持"
    fwd = dy * _forward_dir(camp)
    if fwd > 0.4 * dist:
        return "前压"
    if fwd < -0.4 * dist:
        return "回防"
    return "横移"


def event_response(store: TacticalStore, school: str, rtype: str = "",
                   horizon: int = HORIZON_DEFAULT,
                   kinds: Optional[List[str]] = None,
                   limit_games: int = 0) -> List[EventBehaviorOut]:
    """Across the league, respond to each trigger kind for ``school``.

    For every trigger event on the school's side, look at each robot of
    ``rtype`` ('' = all mobile) and classify its net motion over the next
    ``horizon`` seconds.  Behaviours are aggregated per (event kind).
    """
    gids = store.game_ids_for_school(school)
    if limit_games > 0:
        gids = gids[:limit_games]

    per_kind: Dict[str, Dict] = {}
    cases: Dict[str, List[BehaviorCase]] = {}

    for gid in gids:
        camp = store.camp_of(gid, school)
        if not camp:
            continue
        game = store.game(gid)
        if game.T == 0:
            continue
        seconds = store.seconds(gid)
        for ev in detect_events(store, gid, kinds=kinds):
            if ev.camp != camp:
                continue
            key = ev.kind
            agg = per_kind.setdefault(key, dict(counts={}, n=0, matches=set()))
            agg["matches"].add(gid)
            h_end = min(game.T, int(ev.t) + horizon)
            if h_end <= ev.t:
                continue
            for rid, st in seconds[int(ev.t)].robots.items():
                if st["camp"] != camp or not st["alive"]:
                    continue
                if rtype and st["rtype"] != rtype:
                    continue
                if abs(st["x"]) < 1e-6 and abs(st["y"]) < 1e-6:
                    continue
                end_st = seconds[h_end].robots.get(rid)
                if not end_st or not end_st["alive"]:
                    behaviour = "阵亡"
                else:
                    behaviour = classify_motion(
                        st["x"], st["y"], end_st["x"], end_st["y"], camp)
                agg["counts"][behaviour] = agg["counts"].get(behaviour, 0) + 1
                agg["n"] += 1
                cases.setdefault(key, []).append(BehaviorCase(
                    game_id=gid, t=float(ev.t),
                    opponent=store.opponent_of(gid, school),
                    robot_id=rid, rtype=st["rtype"], detail=behaviour))

    out = []
    for kind, agg in per_kind.items():
        n = agg["n"]
        total = max(n, 1)
        dist = {k: round(100.0 * v / total, 1)
                for k, v in sorted(agg["counts"].items(),
                                   key=lambda kv: -kv[1])}
        out.append(EventBehaviorOut(
            event=kind, team_id=school, horizon_s=horizon,
            behaviors=dist, n=n, n_matches=len(agg["matches"]),
            cases=cases.get(kind, []),
        ))
    out.sort(key=lambda o: -o.n)
    return out
