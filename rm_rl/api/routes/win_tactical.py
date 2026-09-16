"""Tactical WinQ API routes.

POST /api/win/tactical    -> current win + BC action win + top candidates
POST /api/win/targets     -> per-target counterfactual
POST /api/win/fire        -> fire vs hold fire
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...win.predictor import WinPredictor
from ...win.winq import WinQ
from ...win.support import ActionSupport
from .deps import get_state

router = APIRouter(tags=["win"])

_predictor: Optional[WinPredictor] = None
_winq: Optional[WinQ] = None
_support: Optional[ActionSupport] = None


def _get_models(state):
    global _predictor, _winq, _support
    from ...data import features as F
    if _predictor is None:
        wp = WinPredictor(F.obs_dim("步兵3"))
        if not wp.load():
            raise HTTPException(501, "win predictor not trained")
        _predictor = wp
    if _winq is None:
        wq = WinQ(state_dim=161, act_dim=10)
        if not wq.load():
            raise HTTPException(501, "WinQ not trained (run `python -m rm_rl.win.train_winq`)")
        _winq = wq
    if _support is None:
        # fit kNN support on training actions
        import json, sqlite3
        from ...data import build_dataset as BD, features as F
        from ...data import schema as S
        from ...data.team_prior import TeamPrior
        from ...data.vis_map import VisibilityMap
        splits_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))), "splits", "win_split.json")
        train_actions = []
        try:
            with open(splits_file) as f:
                tr_games = json.load(f)["random"]["train"]
            db = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))), "dataset",
                "rmuc_2026_region_dataset.sqlite")
            con = sqlite3.connect(db)
            vmap_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))), "data", "vis_map.npz")
            pr_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))), "data", "team_prior.json")
            vmap = VisibilityMap.load(vmap_path) if os.path.isfile(vmap_path) else None
            pr = TeamPrior.load(pr_path) if os.path.isfile(pr_path) else None
            for gid in tr_games[:50]:  # subsample
                try:
                    game = BD.load_game_arrays(con, gid)
                except Exception:
                    continue
                for camp in (S.CAMP_RED, S.CAMP_BLUE):
                    sf = pr.feats(gid, camp) if pr else np.zeros(6, np.float32)
                    try:
                        act = F.build_action_raw(game, camp, "步兵3",
                                                 action_mode="tactical", goal_horizon=5)
                    except Exception:
                        continue
                    idx = np.linspace(0, len(act)-1, 20).astype(int)
                    for i in idx:
                        train_actions.append(act[i].astype(np.float32))
            con.close()
        except Exception as e:
            print(f"[support] fit failed: {e}")
        if train_actions:
            _support = ActionSupport(train_actions=np.stack(train_actions))
        else:
            _support = ActionSupport()
    return _predictor, _winq, _support


class TacticalReq(BaseModel):
    game_id: int
    t: int
    camp: str = "红"
    rtype: str = "步兵3"


@router.post("/win/tactical")
def tactical_eval(req: TacticalReq, state=Depends(get_state)):
    wp, wq, sup = _get_models(state)
    rl = state.rl
    try:
        obs = rl.obs_at(req.game_id, req.t, req.rtype, req.camp)
    except ValueError as e:
        raise HTTPException(422, str(e))

    cur_p = wp.predict(obs, calibrated=True)

    # BC action
    bc_cmd = None
    bc_p = None
    try:
        bc_cmd = rl.runner("bc").step(obs)
        a_bc = _encode_action(bc_cmd)
        bc_p = wq.predict(obs, a_bc, calibrated=True)
    except Exception:
        pass

    # build candidates
    candidates = []
    if bc_cmd is not None:
        candidates.append(dict(source="bc",
                               goal_dx=bc_cmd.get("goal_dx", 0),
                               goal_dy=bc_cmd.get("goal_dy", 0),
                               fire=bool(bc_cmd.get("fire", False)),
                               target=int(np.argmax(bc_cmd.get("target_probs", [0]))),
                               a=a_bc))
    # rule candidates: hold, advance, retreat, left, right
    for name, gx, gy in [
        ("hold", 0.0, 0.0),
        ("advance", 3.0, 0.0),
        ("retreat", -3.0, 0.0),
        ("left", 0.0, 3.0),
        ("right", 0.0, -3.0),
    ]:
        a_rule = a_bc.copy() if bc_cmd else np.zeros(10, np.float32)
        a_rule[0] = gx; a_rule[1] = gy
        candidates.append(dict(source="rule", name=name,
                               goal_dx=gx, goal_dy=gy,
                               fire=bool(a_rule[2] > 0.5),
                               target=int(np.argmax(a_rule[3:])),
                               a=a_rule))

    # evaluate all candidates in batch
    A = np.stack([c["a"] for c in candidates])
    S = np.tile(obs[None, :], (len(candidates), 1))
    probs = wq.predict_batch(S, A, calibrated=True)
    probs_raw = wq.predict_batch(S, A, calibrated=False)

    out_cands = []
    for i, c in enumerate(candidates):
        s = sup.support_score(c["a"])
        out_cands.append(dict(
            source=c["source"],
            name=c.get("name", c["source"]),
            goal_dx=round(float(c["goal_dx"]), 3),
            goal_dy=round(float(c["goal_dy"]), 3),
            fire=bool(c["fire"]),
            target=c["target"],
            win_prob=round(float(probs[i]), 4),
            delta_pp=round(float((probs[i] - cur_p) * 100), 2),
            support_score=s["support_score"],
            knn_distance=s["knn_distance"],
            ood=s["ood"],
            confidence=s["confidence"],
        ))
    # sort: non-OOD first, then by win_prob
    out_cands.sort(key=lambda x: (x["ood"], -x["win_prob"]))

    return dict(
        current_win_prob=round(float(cur_p), 4),
        bc_win_prob=round(float(bc_p), 4) if bc_p else None,
        candidates=out_cands,
        note="条件胜率估计（observational），非因果效应。OOD 动作不自动推荐。",
    )


@router.post("/win/targets")
def target_eval(req: TacticalReq, state=Depends(get_state)):
    wp, wq, sup = _get_models(state)
    rl = state.rl
    try:
        obs = rl.obs_at(req.game_id, req.t, req.rtype, req.camp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cur_p = wp.predict(obs, calibrated=True)
    bc_cmd = rl.runner("bc").step(obs)
    base_a = _encode_action(bc_cmd)
    targets = ["英雄", "工程", "步兵3", "步兵4", "空中", "哨兵", "无目标"]
    results = []
    A = []
    for ti, name in enumerate(targets):
        a = base_a.copy()
        a[3:] = 0.0; a[3 + ti] = 1.0
        A.append(a)
    S = np.tile(obs[None, :], (len(targets), 1))
    probs = wq.predict_batch(S, np.stack(A), calibrated=True)
    for ti, name in enumerate(targets):
        s = sup.support_score(A[ti])
        results.append(dict(
            target=name,
            win_prob=round(float(probs[ti]), 4),
            delta_pp=round(float((probs[ti] - cur_p) * 100), 2),
            support_score=s["support_score"],
            ood=s["ood"],
            confidence=s["confidence"],
        ))
    results.sort(key=lambda x: -x["win_prob"])
    return dict(current_win_prob=round(float(cur_p), 4), targets=results)


@router.post("/win/fire")
def fire_eval(req: TacticalReq, state=Depends(get_state)):
    wp, wq, sup = _get_models(state)
    rl = state.rl
    try:
        obs = rl.obs_at(req.game_id, req.t, req.rtype, req.camp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cur_p = wp.predict(obs, calibrated=True)
    bc_cmd = rl.runner("bc").step(obs)
    a_free = _encode_action(bc_cmd)
    a_hold = a_free.copy(); a_hold[2] = 0.0
    a_free[2] = 1.0
    pf = wq.predict(obs, a_free, calibrated=True)
    ph = wq.predict(obs, a_hold, calibrated=True)
    return dict(
        current_win_prob=round(float(cur_p), 4),
        weapons_free=dict(win_prob=round(float(pf), 4),
                          delta_pp=round(float((pf - cur_p) * 100), 2)),
        hold_fire=dict(win_prob=round(float(ph), 4),
                       delta_pp=round(float((ph - cur_p) * 100), 2)),
        delta_pp=round(float((pf - ph) * 100), 2),
    )


def _encode_action(cmd: dict) -> np.ndarray:
    """Encode BC command into the 10-D tactical action vector."""
    a = np.zeros(10, np.float32)
    a[0] = float(cmd.get("goal_dx", 0.0))
    a[1] = float(cmd.get("goal_dy", 0.0))
    a[2] = 1.0 if cmd.get("fire", False) else 0.0
    tp = cmd.get("target_probs")
    if tp is not None and len(tp) >= 7:
        a[3:3+7] = np.asarray(tp[:7], np.float32)
    else:
        t = int(cmd.get("target", 6))
        a[3 + min(t, 6)] = 1.0
    return a
