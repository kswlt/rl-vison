"""Win-probability API routes.

GET /api/win/current?game_id=&t=&camp=        -> calibrated P(win|s)
GET /api/win/history?game_id=&camp=           -> per-second win probability curve
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from ...win.predictor import WinPredictor
from .deps import get_state

router = APIRouter(tags=["win"])

_predictor: Optional[WinPredictor] = None
_predictor_camp: Optional[str] = None  # the side the obs is built for (infantry3)


def get_predictor(state) -> WinPredictor:
    global _predictor
    if _predictor is None:
        from ...data import features as F
        in_dim = F.obs_dim("步兵3")
        wp = WinPredictor(in_dim)
        if wp.load():
            _predictor = wp
        else:
            raise HTTPException(501, "win predictor not trained (run `python -m rm_rl.win.train`)")
    return _predictor


@router.get("/win/current")
def win_current(
    game_id: int = Query(...),
    t: int = Query(...),
    camp: str = Query("红"),
    state=Depends(get_state),
):
    """Calibrated win probability for `camp` at second `t`."""
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game {game_id} not found")
    pred = get_predictor(state)
    rl = state.rl
    try:
        obs = rl.obs_at(game_id, int(t), "步兵3", camp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    p = pred.predict(obs, calibrated=True)
    p_raw = pred.predict(obs, calibrated=False)
    return {
        "game_id": game_id, "t": int(t), "camp": camp,
        "win_prob": round(float(p), 4),
        "win_prob_raw": round(float(p_raw), 4),
        "temperature": pred.temperature,
    }


@router.get("/win/history")
def win_history(
    game_id: int = Query(...),
    camp: str = Query("红"),
    step: int = Query(2, ge=1, le=10),
    state=Depends(get_state),
):
    """Per-second win probability curve for the whole game (one camp)."""
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game {game_id} not found")
    pred = get_predictor(state)
    rl = state.rl
    game = rl._load_game(game_id)
    T = game.T
    if T <= 0:
        return {"game_id": game_id, "camp": camp, "times": [], "probs": []}
    times, probs = [], []
    for t in range(1, T + 1, step):
        try:
            obs = rl.obs_at(game_id, t, "步兵3", camp)
            p = pred.predict(obs, calibrated=True)
        except Exception:
            continue
        times.append(int(t))
        probs.append(round(float(p), 4))
    return {"game_id": game_id, "camp": camp, "times": times, "probs": probs}
