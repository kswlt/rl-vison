"""Team endpoints: registry, profile, matches."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...tactical import analytics as A
from ...tactical.conditions import Condition
from ...tactical.formations import formation_stats_summary, formation_series
from ...tactical.opponent import opponent_profile
from ...tactical.schemas import (MatchOut, TeamMatchOut, TeamOut,
                                 TeamProfileOut)
from .deps import get_state

router = APIRouter(tags=["teams"])


def _resolve(state, team_id: str) -> str:
    """Resolve an alias/school name to a canonical team id (404 if unknown)."""
    tid = state.identity.resolve(team_id)
    if not tid or tid not in state.identity.all_team_ids():
        raise HTTPException(404, f"unknown team {team_id}")
    return tid


@router.get("/teams", response_model=list[TeamOut])
def list_teams(state=Depends(get_state)):
    out = []
    for tid in state.identity.all_team_ids():
        m = state.store.matches()
        cnt = int(((m.red_school == tid) | (m.blue_school == tid)).sum())
        wins = int(((m.red_school == tid) & (m.winner == "红")).sum() |
                   ((m.blue_school == tid) & (m.winner == "蓝")).sum())
        row = state.identity.to_dict(tid)
        row["match_count"] = cnt
        row["win_rate"] = round(wins / max(cnt, 1), 3)
        out.append(TeamOut(**row))
    out.sort(key=lambda t: -t.match_count)
    return out


@router.get("/teams/{team_id}", response_model=TeamOut)
def get_team(team_id: str, state=Depends(get_state)):
    team_id = _resolve(state, team_id)
    m = state.store.matches()
    cnt = int(((m.red_school == team_id) | (m.blue_school == team_id)).sum())
    wins = int(((m.red_school == team_id) & (m.winner == "红")).sum() |
               ((m.blue_school == team_id) & (m.winner == "蓝")).sum())
    row = state.identity.to_dict(team_id)
    row["match_count"] = cnt
    row["win_rate"] = round(wins / max(cnt, 1), 3)
    return TeamOut(**row)


@router.get("/teams/{team_id}/profile", response_model=TeamProfileOut)
def team_profile(team_id: str, state=Depends(get_state)):
    team_id = _resolve(state, team_id)
    return opponent_profile(state, team_id)


@router.get("/teams/{team_id}/matches", response_model=list[TeamMatchOut])
def team_matches(team_id: str, state=Depends(get_state)):
    team_id = _resolve(state, team_id)
    m = state.store.matches()
    sel = m[(m.red_school == team_id) | (m.blue_school == team_id)]
    out = []
    for _, r in sel.iterrows():
        camp = "红" if r.red_school == team_id else "蓝"
        opponent = r.blue_school if camp == "红" else r.red_school
        out.append(TeamMatchOut(
            game_id=int(r.game_id), region=str(r.region),
            round_no=int(r.round_no), opponent=str(opponent), camp=camp,
            winner=str(r.winner), duration=int(r.duration),
            started_at=str(r.started_at or ""),
            won=(r.winner == camp),
        ))
    out.sort(key=lambda x: -x.game_id)
    return out


# keep the module importable for tests that import formation helpers
__all__ = ["router", "formation_stats_summary", "formation_series", "Condition"]
