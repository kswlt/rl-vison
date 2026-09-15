"""Rule-based tactical brief (Milestone 10).

Deterministic summariser over the *real* statistics already produced by the
platform (opponent profile vs league average, opening flow field, event
response after outpost pressure).  No online LLM, no fabricated conclusions:
every point carries its samples (n), number of matches and, where available,
the real case list.  Output is explicitly framed as historical statistics +
heuristic advice, never as a guaranteed winning strategy.
"""
from __future__ import annotations

import math
import time
from typing import Dict, List

from . import events as EV
from . import opponent as OP
from .analytics import TacticalStore
from .conditions import Condition
from .flow import flow_field
from .schemas import TacticalBriefOut, BriefSection, BriefPoint

MIN_SAMPLE = 5          # below this, points are flagged "样本不足"
LEAGUE_DELTA = 0.25     # relative difference that counts as "显著"


def _pct_diff(v: float, base: float) -> float:
    return (v - base) / max(abs(base), 1e-6)


def _rate(text: str, pct: float, n: int, n_matches: int) -> str:
    return f"{text}：{pct:.0f}%（n={n}，来自 {n_matches} 场比赛）"


def _advice_point(point_id: str, title: str, finding: str, advice: str,
                  n: int, n_matches: int, metric: Dict = None,
                  cases: List = None) -> BriefPoint:
    insufficient = n < MIN_SAMPLE
    return BriefPoint(
        id=point_id, title=title,
        finding=finding + ("（样本不足，仅供参考）" if insufficient else ""),
        advice=advice,
        n=n, n_matches=n_matches,
        insufficient=insufficient,
        metric=metric or {},
        cases=[dict(c) for c in (cases or [])][:6],
    )


def tactical_brief(store: TacticalStore, school: str,
                   sample_league: int = 30) -> TacticalBriefOut:
    s: TacticalStore = getattr(store, "store", store)
    gids = s.game_ids_for_school(school)
    n_matches_total = len(gids)
    profile = OP.opponent_profile(s, school)
    league = OP._league_avgs(s, sample_limit=sample_league)
    m = {x.key: x.value for x in profile.metrics}

    sections: List[BriefSection] = []

    # -- opening ------------------------------------------------------------
    opening_points: List[BriefPoint] = []
    try:
        fl = flow_field(s, Condition(rtype="", phase="open30"),
                        school=school)
        if fl.n >= MIN_SAMPLE:
            half = fl.nx // 2
            n_r = sum(c.n for c in fl.cells if c.x >= half)
            n_l = sum(c.n for c in fl.cells if c.x < half)
            if n_r + n_l > 0:
                r_share = 100.0 * n_r / (n_r + n_l)
                lv = 50.0
                opening_points.append(_advice_point(
                    "open_side", "开局站位",
                    _rate(f"开局 0-30s 右半场活动占比", r_share, fl.n,
                          fl.n_matches),
                    ("右路活动显著（" + (">" if r_share > lv else "<") +
                     f"联盟均衡 50%" + ("，优先控制中左，避免无准备正面争右" if r_share > 60
                      else "，可尝试从对方弱侧发起" if r_share < 40 else "，保持中线拉扯") +
                     "）"),
                    fl.n, fl.n_matches,
                    metric=dict(right_share=round(r_share, 1),
                                left_share=round(100 - r_share, 1))))
    except Exception:
        pass
    front = m.get("front_occupancy", float("nan"))
    if not math.isnan(front) and league.get("front_occupancy"):
        if _pct_diff(front, league["front_occupancy"]) > LEAGUE_DELTA:
            opening_points.append(_advice_point(
                "open_front", "开局前压",
                _rate(f"前场占位率 {front:.0f}%（联盟平均 "
                      f"{league['front_occupancy']:.0f}%）", front,
                      n_matches_total, n_matches_total),
                "该队开局倾向压前场，注意其早期推进节奏，避免在己方半场被动接战",
                n_matches_total, n_matches_total,
                metric=dict(value=round(front, 1),
                            league=round(league["front_occupancy"], 1))))
    if opening_points:
        sections.append(BriefSection(id="opening", title="开局",
                                     summary="开局站位与前压特点",
                                     points=opening_points))

    # -- outpost pressure ---------------------------------------------------
    op_points: List[BriefPoint] = []
    try:
        resp = EV.event_response(s, school, rtype="", horizon=15,
                                 kinds=["outpost_lt50"])
        for r in resp:
            if r.n < MIN_SAMPLE:
                continue
            fb = r.behaviors.get("回防", 0.0)
            hold = r.behaviors.get("保持", 0.0)
            push = r.behaviors.get("前压", 0.0)
            top = max([("回防", fb), ("保持", hold), ("前压", push)],
                      key=lambda kv: kv[1])
            if fb >= 55.0:
                advice = "可以利用前哨压力诱导阵型回缩，为其他路线创造空间"
            elif push >= 55.0:
                advice = "前哨受压后仍会前压，注意保护前哨、防其乘势推进"
            else:
                advice = "前哨受压后行为较分散，难以单点诱导，注意多线拉扯"
            op_points.append(_advice_point(
                "outpost_resp", "前哨受压（HP<50%）后 15s",
                _rate(f"回防 {fb:.0f}% / 保持 {hold:.0f}% / "
                      f"前压 {push:.0f}%", top[1], r.n, r.n_matches),
                advice, r.n, r.n_matches,
                metric=dict(回防=round(fb, 1), 保持=round(hold, 1),
                            前压=round(push, 1)),
                cases=[dict(game_id=c.game_id, t=c.t, opponent=c.opponent,
                            behavior=c.detail) for c in r.cases]))
    except Exception as e:            # pragma: no cover - diagnostic path
        import traceback
        traceback.print_exc()
    if op_points:
        sections.append(BriefSection(id="outpost", title="前哨受压",
                                     summary="前哨 HP<50% 后的响应行为",
                                     points=op_points))

    # -- endgame ------------------------------------------------------------
    eg_points: List[BriefPoint] = []
    shrink = m.get("endgame_shrink", float("nan"))
    if not math.isnan(shrink) and league.get("endgame_shrink"):
        rel = _pct_diff(shrink, league["endgame_shrink"])
        if abs(rel) > LEAGUE_DELTA:
            insufficient = n_matches_total < MIN_SAMPLE
            eg_points.append(BriefPoint(
                id="eg_shrink", title="残局阵型",
                finding=(f"残局收缩程度 {shrink:.2f}（联盟平均 "
                         f"{league['endgame_shrink']:.2f}）"
                         + ("（样本不足，仅供参考）" if insufficient else "")),
                advice=("该队残局明显收缩，增加横向拉扯避免进入其重叠火力区"
                        if rel > 0 else
                        "该队残局收缩弱于联盟，可考虑在最后阶段拉开宽度消耗其协同"),
                n=n_matches_total, n_matches=n_matches_total,
                insufficient=insufficient,
                metric=dict(value=round(shrink, 2),
                            league=round(league["endgame_shrink"], 2))))
    posfix = m.get("position_fix", float("nan"))
    if not math.isnan(posfix) and league.get("position_fix"):
        if posfix > league["position_fix"] * 1.2 and posfix > 25:
            eg_points.append(_advice_point(
                "eg_fixed", "位置依赖",
                _rate(f"固定位置依赖 {posfix:.0f}%（联盟平均 "
                      f"{league['position_fix']:.0f}%）", posfix,
                      n_matches_total, n_matches_total),
                "该队站位较固定，可针对性预判其转点路线并埋伏",
                n_matches_total, n_matches_total,
                metric=dict(value=round(posfix, 1),
                            league=round(league["position_fix"], 1))))
    if eg_points:
        sections.append(BriefSection(id="endgame", title="残局",
                                     summary="残局收缩与站位依赖",
                                     points=eg_points))

    return TacticalBriefOut(
        team=school, n_matches=n_matches_total,
        generated_at=time.strftime("%Y-%m-%d %H:%M"),
        sections=sections,
        note="全部结论基于官方日志历史统计（非未来预测），样本量与比赛数已逐条标注；"
             "建议仅用于赛前参考与复盘讨论。",
    )
