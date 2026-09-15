"""Condition definitions for conditional tactical analytics.

A "condition" is a declarative filter over per-second game states, mirroring the
product language of the dashboard (阶段 / 结构状态 / 人数状态 / 机器人状态).
Conditions are evaluated against lightweight per-second summaries so the heavy
aggregations (heatmaps, flow fields, event responses) share one code path.

All conditions return a boolean mask over the seconds of one game.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..data import schema as S

# ---------------------------------------------------------------------------
# Phase presets (seconds from game start; duration-aware)
# ---------------------------------------------------------------------------
PHASE_PRESETS = {
    "open30": ("0-30s", lambda d: (0, 30)),
    "early30_120": ("30-120s", lambda d: (30, 120)),
    "mid": ("中期", lambda d: (max(120, d // 4), max(120, d // 2))),
    "final120": ("最后120s", lambda d: (max(0, d - 120), d)),
    "final90": ("最后90s", lambda d: (max(0, d - 90), d)),
    "final60": ("最后60s", lambda d: (max(0, d - 60), d)),
}

# outpost HP fractions (of max HP) that define structure-state buckets
OUTPOST_FRACS = (0.75, 0.50, 0.25)


@dataclass
class Condition:
    """One declarative filter. ``phase`` is a preset key or "custom"."""

    rtype: str = ""                    # "" = all mobile types
    phase: str = ""                    # preset key from PHASE_PRESETS, or custom
    phase_custom: tuple = ()           # (t0, t1) when phase == "custom"
    outpost: str = ""                  # full / lt75 / lt50 / lt25 / dead
    base_hit: bool = False             # own base took damage this second
    numbers: str = ""                  # full / self_down / enemy_down / adv / disadv
    robot_hp: str = ""                 # low / high
    robot_ammo: str = ""               # low / high
    camp: str = ""                     # whose perspective ("红"/"蓝"/"")
    school: str = ""                   # optional school filter (team)

    def label(self) -> str:
        parts = []
        if self.phase:
            parts.append(PHASE_PRESETS.get(self.phase, (self.phase,))[0])
        if self.outpost:
            parts.append(f"前哨{self.outpost}")
        if self.base_hit:
            parts.append("基地受击")
        if self.numbers:
            parts.append(self.numbers)
        if self.robot_hp:
            parts.append(f"血量{self.robot_hp}")
        if self.robot_ammo:
            parts.append(f"弹量{self.robot_ammo}")
        return "+".join(parts) or "全部"


# ---------------------------------------------------------------------------
# Per-second summary builder (one game)
# ---------------------------------------------------------------------------
@dataclass
class SecondSummary:
    t: int
    duration: int
    # structure
    outpost_hp: Dict[str, float] = field(default_factory=dict)   # camp -> hp
    outpost_max: Dict[str, float] = field(default_factory=dict)
    base_hp: Dict[str, float] = field(default_factory=dict)
    base_max: Dict[str, float] = field(default_factory=dict)
    base_hit: Dict[str, bool] = field(default_factory=dict)      # camp -> hit
    # numbers (mobile units alive, excluding buildings)
    alive: Dict[str, int] = field(default_factory=dict)
    # robot states for the ego camp's machines
    robots: Dict[int, Dict] = field(default_factory=dict)        # robot_id -> state


def build_seconds(game) -> Dict[int, SecondSummary]:
    """Collapse one GameArrays into per-second summaries.

    ``game`` is the time-aligned per-entity structure from
    ``rm_rl.data.build_dataset.load_game_arrays``.
    """
    T = game.T
    dur = T
    out: Dict[int, SecondSummary] = {}
    # robot_id -> (rtype, camp)
    kinds = {}
    for rid, e in game.ent.items():
        camp = S.CAMP_BLUE if rid > 100 else S.CAMP_RED
        rtype = _rtype_for_rid(rid)
        kinds[rid] = (rtype, camp)
    # base-hit detection: a hit event targeting the base would live in the
    # events table, which the summary does not see; we approximate by a large
    # instantaneous HP drop of the base building.
    for rid, (rtype, camp) in kinds.items():
        if rtype != S.TYPE_BASE:
            continue
        e = game.ent[rid]
        hp = e.hp
        dropped = (hp[:-1] - hp[1:]) > 20.0
        for t in range(1, T):
            s = out.setdefault(t, SecondSummary(t=t, duration=dur))
            s.base_hit[camp] = s.base_hit.get(camp, False) or bool(dropped[t - 1])
    for t in range(1, T + 1):
        s = out.setdefault(t, SecondSummary(t=t, duration=dur))
        for rid, (rtype, camp) in kinds.items():
            e = game.ent[rid]
            if rtype == S.TYPE_BASE:
                s.base_hp[camp] = float(e.hp[t - 1])
                s.base_max[camp] = float(e.maxhp[t - 1])
            elif rtype == S.TYPE_OUTPOST:
                s.outpost_hp[camp] = float(e.hp[t - 1])
                s.outpost_max[camp] = float(e.maxhp[t - 1])
            else:
                if e.alive[t - 1] > 0:
                    s.alive[camp] = s.alive.get(camp, 0) + 1
                s.robots[rid] = dict(
                    rtype=rtype, camp=camp, x=float(e.x[t - 1]),
                    y=float(e.y[t - 1]), hp=float(e.hp[t - 1]),
                    maxhp=float(e.maxhp[t - 1]), alive=int(e.alive[t - 1]),
                    ammo=float(e.ammo17[t - 1]),
                )
    return out


def _rtype_for_rid(rid: int) -> str:
    rid = rid if rid <= 100 else rid - 100
    for rtype, base in S.RED_ID.items():
        if base == rid:
            return rtype
    return "未知"


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------
def mask_seconds(cond: Condition, game, seconds: Optional[Dict[int, SecondSummary]] = None) -> Dict[int, bool]:
    """Boolean mask over game seconds satisfying ``cond`` (team perspective)."""
    seconds = seconds or build_seconds(game)
    camp = cond.camp or S.CAMP_RED
    ecamp = S.enemy_camp(camp)
    T = game.T
    mask: Dict[int, bool] = {}

    # phase window
    if cond.phase == "custom" and cond.phase_custom:
        t0, t1 = int(cond.phase_custom[0]), int(cond.phase_custom[1])
    elif cond.phase in PHASE_PRESETS:
        _label, fn = PHASE_PRESETS[cond.phase]
        t0, t1 = fn(T)
    else:
        t0, t1 = 0, T

    for t in range(max(1, t0 + 1), min(T, t1) + 1):
        s = seconds[t]
        ok = True
        # structure
        if cond.outpost:
            hp = s.outpost_hp.get(camp, 0.0)
            mx = s.outpost_max.get(camp, 1.0) or 1.0
            frac = hp / mx if mx > 0 else 0.0
            if cond.outpost == "full":
                ok = ok and frac > 0.999
            elif cond.outpost == "dead":
                ok = ok and hp <= 0.0
            elif cond.outpost == "lt75":
                ok = ok and 0 < frac < 0.75
            elif cond.outpost == "lt50":
                ok = ok and 0 < frac < 0.50
            elif cond.outpost == "lt25":
                ok = ok and 0 < frac < 0.25
        if cond.base_hit and not s.base_hit.get(camp, False):
            ok = False
        # numbers
        if cond.numbers:
            own = s.alive.get(camp, 0)
            opp = s.alive.get(ecamp, 0)
            if cond.numbers == "full":
                ok = ok and own >= 6 and opp >= 6
            elif cond.numbers == "self_down":
                ok = ok and own < 6 and opp >= 6
            elif cond.numbers == "enemy_down":
                ok = ok and own >= 6 and opp < 6
            elif cond.numbers == "adv":
                ok = ok and own > opp
            elif cond.numbers == "disadv":
                ok = ok and own < opp
        # robot-state conditions are about *any* robot of the ego camp of the
        # given type; for per-robot analytics the caller filters per robot too
        if cond.robot_hp or cond.robot_ammo:
            any_ok = False
            for rid, st in s.robots.items():
                if st["camp"] != camp:
                    continue
                if cond.rtype and st["rtype"] != cond.rtype:
                    continue
                if not st["alive"]:
                    continue
                hp_ok = ammo_ok = True
                if cond.robot_hp:
                    frac = st["hp"] / (st["maxhp"] or 1.0)
                    hp_ok = (frac < 0.3) if cond.robot_hp == "low" else (frac > 0.7)
                if cond.robot_ammo:
                    ammo_ok = (st["ammo"] < 20) if cond.robot_ammo == "low" else (st["ammo"] > 100)
                if hp_ok and ammo_ok:
                    any_ok = True
                    break
            ok = ok and any_ok
        mask[t] = ok
    return mask
