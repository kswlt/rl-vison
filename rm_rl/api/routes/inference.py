"""RL inference endpoints (Milestone 8).

Wires the real trained BC / IQL / DT checkpoints through the project's own
feature builder (``build_obs``, full 161-D constructor incl. vis_map +
team_prior) and deployment wrapper (``MLPPolicyRunner``).  When no checkpoint
is available the endpoint returns 501 with an honest "model not loaded" —
never a fake model, never fabricated numbers.

Disagreement analysis compares the policy suggestion against what the human
actually did (from the log) and reports *disagreement*, explicitly not
"AI is right".
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from ...data import schema as S
from ...tactical import rl as R
from ...tactical.schemas import (DisagreementItem, DisagreementOut,
                                 InferenceOut)
from .deps import get_state

router = APIRouter(tags=["inference"])

TARGET_LABELS = {i: name for i, name in
                 enumerate(S.MOBILE_TYPES + ["无目标"])}


@router.post("/inference", response_model=InferenceOut)
def inference(req: dict, state=Depends(get_state)):
    game_id = int(req.get("game_id", 0))
    t = float(req.get("t", 0.0))
    camp = str(req.get("camp", "红"))
    rtype = str(req.get("rtype", "步兵3"))
    algo = str(req.get("algo", "iql"))
    if algo not in R.MODEL_LABELS:
        raise HTTPException(422, f"unknown algo {algo} (bc|iql|dt)")
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    if not R.model_available(algo):
        raise HTTPException(
            501, f"模型未加载（{R.MODEL_LABELS[algo]}）：{R.MODEL_DIRS[algo]} 下没有 "
                 "best.pt/final.pt，请先运行训练管线 rm_rl/train 或放置权重。")

    rl = state.rl
    t = int(round(t))
    try:
        obs = rl.obs_at(game_id, t, rtype, camp)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cmd = rl.runner(algo).step(obs)
    human = rl.human_action(game_id, t, rtype, camp)
    agree = dict(score=rl.disagreement(human, cmd))

    target = cmd.get("target")
    target_label = TARGET_LABELS.get(target, "无目标") if target is not None else "无目标"
    return InferenceOut(
        game_id=game_id, t=float(t), algo=algo,
        goal_dx=float(cmd.get("goal_dx", 0.0)),
        goal_dy=float(cmd.get("goal_dy", 0.0)),
        fire=bool(cmd.get("fire", False)),
        p_fire=float(cmd.get("fire", 0.0)),
        target=target, target_label=target_label,
        target_conf=float(cmd.get("target_conf", 0.0)),
        target_probs=[float(x) for x in cmd.get("target_probs", [])],
        human=human or {}, agree=agree,
    )


@router.post("/inference/disagreements", response_model=DisagreementOut)
def disagreements(state=Depends(get_state),
                  game_id: int = Query(...),
                  algo: str = Query("iql"),
                  rtype: str = Query("步兵3"),
                  top_k: int = Query(20, ge=1, le=100),
                  step: int = Query(1, ge=1, le=30)):
    """Scan one game for the seconds where human vs AI differ most."""
    if algo not in R.MODEL_LABELS:
        raise HTTPException(422, f"unknown algo {algo}")
    if not R.model_available(algo):
        raise HTTPException(501, f"模型未加载（{R.MODEL_LABELS[algo]}）")
    match = state.store.match(game_id)
    if match is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    T = match.T if hasattr(match, "T") else 0
    if T <= 0:
        raise HTTPException(422, "game has no data")

    rl = state.rl
    camps = [S.CAMP_RED, S.CAMP_BLUE]
    items: list[DisagreementItem] = []
    t0 = time.time()
    for camp in camps:
        for t in range(1, T + 1, step):
            try:
                obs = rl.obs_at(game_id, t, rtype, camp)
                cmd = rl.runner(algo).step(obs)
                human = rl.human_action(game_id, t, rtype, camp)
            except Exception:
                continue
            if not human or not human.get("alive", False):
                continue
            score = rl.disagreement(human, cmd)
            if score >= 0.4:
                items.append(DisagreementItem(
                    game_id=game_id, t=float(t), score=score, rtype=rtype,
                    camp=camp, ai=dict(cmd), human=human))
    items.sort(key=lambda x: -x.score)
    items = items[:top_k]
    return DisagreementOut(
        model=algo, items=items,
        note=f"扫描 {T}s 秒（step={step}）耗时 {time.time() - t0:.1f}s；"
             "分数越大表示 AI 与真人分歧越大，仅提示值得复盘，不表示 AI 更正确。",
    )
