"""Analytics endpoints: conditional heatmap, flow, formation, event response."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...tactical import analytics as A
from ...tactical import events as EV
from ...tactical import flow as FL
from ...tactical.conditions import Condition
from ...tactical.formations import formation_series
from ...tactical.schemas import (EventBehaviorOut, FlowOut, FormationOut,
                                 HeatmapOut)
from .deps import get_state

router = APIRouter(tags=["analytics"])


def _cond(team: str = "", rtype: str = "", phase: str = "",
          t0: Optional[float] = None, t1: Optional[float] = None,
          outpost: str = "", base_hit: bool = False,
          numbers: str = "", robot_hp: str = "", robot_ammo: str = "",
          camp: str = "") -> Condition:
    phase_custom = (t0, t1) if (phase == "custom" and t0 is not None
                                and t1 is not None) else ()
    return Condition(rtype=rtype, phase=phase, phase_custom=phase_custom,
                     outpost=outpost, base_hit=base_hit, numbers=numbers,
                     robot_hp=robot_hp, robot_ammo=robot_ammo, camp=camp)


@router.get("/analytics/heatmap", response_model=HeatmapOut)
def heatmap(state=Depends(get_state),
            team: str = Query("", description="school name or alias"),
            rtype: str = Query("", description="步兵3/步兵4/哨兵/英雄…"),
            phase: str = Query("", description="open30/early30_120/mid/final120/final90/final60/custom"),
            t0: Optional[float] = None, t1: Optional[float] = None,
            outpost: str = Query("", description="full/lt75/lt50/lt25/dead"),
            base_hit: bool = False,
            numbers: str = Query("", description="full/self_down/enemy_down/adv/disadv"),
            robot_hp: str = Query("", description="low/high"),
            robot_ammo: str = Query("", description="low/high"),
            cell_m: float = Query(1.0, ge=0.5, le=4.0),
            limit_games: int = Query(0, ge=0, le=613)):
    school = team
    if team:
        tid = state.identity.resolve(team)
        if not tid:
            raise HTTPException(404, f"unknown team {team}")
        school = tid
    cond = _cond(school, rtype, phase, t0, t1, outpost, base_hit,
                 numbers, robot_hp, robot_ammo)
    params = dict(team=school, rtype=rtype, phase=phase, t0=t0, t1=t1,
                  outpost=outpost, base_hit=base_hit, numbers=numbers,
                  robot_hp=robot_hp, robot_ammo=robot_ammo,
                  cell_m=cell_m, limit_games=limit_games)

    def _compute():
        return A.occupancy_heatmap(state.store, cond, cell_m=cell_m,
                                   school=school, rtype=rtype,
                                   limit_games=limit_games).model_dump()

    data = state.cached("heatmap", params, _compute)
    return HeatmapOut(**data)


@router.get("/analytics/flow", response_model=FlowOut)
def flow(state=Depends(get_state),
         team: str = Query(""), rtype: str = Query(""),
         phase: str = Query(""),
         t0: Optional[float] = None, t1: Optional[float] = None,
         outpost: str = Query(""), numbers: str = Query(""),
         cell_m: float = Query(2.0, ge=1.0, le=4.0),
         limit_games: int = Query(0, ge=0, le=613)):
    school = team
    if team:
        tid = state.identity.resolve(team)
        if not tid:
            raise HTTPException(404, f"unknown team {team}")
        school = tid
    cond = _cond(school, rtype, phase, t0, t1, outpost, False, numbers)
    params = dict(team=school, rtype=rtype, phase=phase, t0=t0, t1=t1,
                  outpost=outpost, numbers=numbers, cell_m=cell_m,
                  limit_games=limit_games)

    def _compute():
        return FL.flow_field(state.store, cond, cell_m=cell_m, school=school,
                             rtype=rtype, limit_games=limit_games).model_dump()

    data = state.cached("flow", params, _compute)
    return FlowOut(**data)


@router.get("/analytics/formation", response_model=FormationOut)
def formation(game_id: int, camp: str = Query("红", pattern="^[红蓝]$"),
              step: int = Query(1, ge=1, le=30), state=Depends(get_state)):
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    return formation_series(state.store, game_id, camp, step=step)


@router.get("/analytics/event-response", response_model=list[EventBehaviorOut])
def event_response(state=Depends(get_state),
                   team: str = Query(..., description="school name or alias"),
                   rtype: str = Query(""),
                   horizon: int = Query(15, ge=5, le=60),
                   kind: str = Query(""),
                   limit_games: int = Query(0, ge=0, le=613)):
    tid = state.identity.resolve(team)
    if not tid:
        raise HTTPException(404, f"unknown team {team}")
    kinds = [kind] if kind else None
    return EV.event_response(state.store, tid, rtype=rtype, horizon=horizon,
                             kinds=kinds, limit_games=limit_games)
