"""Match endpoints: list, detail, timeline, per-second state, events."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...tactical.conditions import build_seconds
from ...tactical.schemas import (EventOut, MatchOut, MatchStateOut,
                                 MatchTimelineOut, RobotStateOut,
                                 TimelinePoint)
from ...tactical.team_identity import normalize
from .deps import get_state

router = APIRouter(tags=["matches"])


def _match_out(state, row) -> MatchOut:
    return MatchOut(
        game_id=int(row.game_id), region=str(row.region),
        match_no=int(row.match_no) if row.match_no else 0,
        round_no=int(row.round_no) if row.round_no else 0,
        red_school=str(row.red_school), blue_school=str(row.blue_school),
        winner=str(row.winner), duration=int(row.duration),
        started_at=str(row.started_at or ""),
        red_team_id=state.identity.resolve(row.red_school) or row.red_school,
        blue_team_id=state.identity.resolve(row.blue_school) or row.blue_school,
    )


@router.get("/matches", response_model=list[MatchOut])
def list_matches(state=Depends(get_state),
                 team: Optional[str] = Query(None, description="school or alias"),
                 region: Optional[str] = None,
                 limit: int = Query(200, ge=1, le=613)):
    m = state.store.matches()
    if team:
        tid = state.identity.resolve(team)
        if not tid:
            raise HTTPException(404, f"unknown team {team}")
        m = m[(m.red_school == tid) | (m.blue_school == tid)]
    if region:
        m = m[m.region == region]
    m = m.sort_values("game_id", ascending=False).head(limit)
    return [_match_out(state, row) for _, row in m.iterrows()]


@router.get("/matches/{game_id}", response_model=MatchOut)
def get_match(game_id: int, state=Depends(get_state)):
    row = state.store.match(game_id)
    if row is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    return _match_out(state, row)


@router.get("/matches/{game_id}/timeline", response_model=MatchTimelineOut)
def match_timeline(game_id: int, state=Depends(get_state)):
    game = state.store.game(game_id)
    if game.T == 0:
        raise HTTPException(404, f"game_id {game_id} has no timeseries")
    seconds = state.store.seconds(game_id)

    # event markers from the events table (compact)
    con = state.store.con
    ev = con.execute(
        'SELECT "时刻秒", "事件类型", "阵营", "机器人类型" FROM events '
        'WHERE game_id=? ORDER BY "时刻秒"', (int(game_id),)).fetchall()
    con.close()
    markers: dict[int, list[str]] = {}
    for t, etype, camp, rtype in ev:
        key = int(t)
        markers.setdefault(key, [])
        label = f"{etype}"
        if camp:
            label = f"{camp}{rtype or ''}{etype}" if rtype else f"{camp}{etype}"
        if label not in markers[key]:
            markers[key].append(label)

    pts = []
    for t in range(1, game.T + 1):
        ms = markers.get(t, [])
        s = seconds[t]
        # structural events derived from state (outpost thresholds)
        for camp in ("红", "蓝"):
            hp = s.outpost_hp.get(camp, 0.0)
            mx = s.outpost_max.get(camp, 1.0) or 1.0
            if mx > 0 and 0 < hp / mx < 0.5 and not (camp in markers and
                                                     f"{camp}前哨<50%" in markers.get(t, [])):
                ms.append(f"{camp}前哨<50%")
        pts.append(TimelinePoint(t=float(t), events=ms))
    return MatchTimelineOut(game_id=game_id, duration=int(game.T), points=pts)


@router.get("/matches/{game_id}/state", response_model=MatchStateOut)
def match_state(game_id: int, t: float = Query(1.0, ge=0),
                state=Depends(get_state)):
    game = state.store.game(game_id)
    if game.T == 0:
        raise HTTPException(404, f"game_id {game_id} has no timeseries")
    idx = int(round(t))
    idx = max(1, min(game.T, idx))
    robots, buildings = [], []
    for rid, e in game.ent.items():
        hp = float(e.hp[idx - 1])
        camp = "蓝" if rid > 100 else "红"
        is_build = rid in (10, 11, 110, 111)
        yaw = float(e.yaw[idx - 1])
        item = RobotStateOut(
            robot_id=rid, rtype=_rtype(rid), camp=camp,
            school="", x=float(e.x[idx - 1]), y=float(e.y[idx - 1]),
            z=float(e.z[idx - 1]), hp=hp, maxhp=float(e.maxhp[idx - 1]),
            yaw=yaw, yaw_ok=abs(yaw - (-140.0)) > 1e-6,
            alive=bool(e.alive[idx - 1]),
            known=(abs(float(e.x[idx - 1])) > 1e-6 or
                   abs(float(e.y[idx - 1])) > 1e-6),
            ammo=float(e.ammo17[idx - 1]), heat=float(e.heat17[idx - 1]),
            vuln=bool(e.vuln[idx - 1]), power=float(e.power[idx - 1]),
        )
        (buildings if is_build else robots).append(item)
    robots.sort(key=lambda r: r.robot_id)
    buildings.sort(key=lambda r: r.robot_id)
    return MatchStateOut(game_id=game_id, t=float(idx), duration=int(game.T),
                         robots=robots, buildings=buildings)


def _rtype(rid: int) -> str:
    from ...data import schema as S
    base = rid if rid <= 100 else rid - 100
    for rtype, b in S.RED_ID.items():
        if b == base:
            return rtype
    return "未知"


@router.get("/matches/{game_id}/events", response_model=list[EventOut])
def match_events(game_id: int, state=Depends(get_state),
                 etype: Optional[str] = None,
                 limit: int = Query(2000, ge=1, le=20000)):
    con = state.store.con
    q = ('SELECT "时刻秒","事件类型","robot_id","机器人类型","阵营","学校名",'
         '"目标robot_id","目标类型","类别","数值","备注" FROM events WHERE game_id=?')
    args: list = [int(game_id)]
    if etype:
        q += ' AND "事件类型"=?'
        args.append(etype)
    q += " ORDER BY \"时刻秒\" LIMIT ?"
    args.append(int(limit))
    rows = con.execute(q, args).fetchall()
    con.close()
    out = []
    for r in rows:
        out.append(EventOut(
            t=float(r[0]), etype=str(r[1]), robot_id=int(r[2] or 0),
            rtype=str(r[3] or ""), camp=str(r[4] or ""), school=str(r[5] or ""),
            target_id=int(r[6]) if r[6] is not None else None,
            target_type=str(r[7] or ""), category=str(r[8] or ""),
            value=float(r[9]) if r[9] is not None else None,
            note=str(r[10] or ""),
        ))
    return out
