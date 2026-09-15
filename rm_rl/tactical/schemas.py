"""Pydantic schemas shared by every API route.

These are the *contracts* between the FastAPI layer and the React frontend.
Keeping them in one module means the API surface and the tactical analytics
layer cannot drift apart: any route returns one of these models and any
analytics function consumes their inputs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
class TeamOut(BaseModel):
    team_id: str
    school_name: str
    team_name: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    match_count: int = 0
    win_rate: float = 0.0


class TeamProfileMetric(BaseModel):
    key: str
    label: str
    value: float
    league_avg: float = 0.0
    top_avg: float = 0.0
    n: int = 0
    n_matches: int = 0
    unit: str = ""
    reliable: bool = True


class TeamProfileOut(BaseModel):
    team_id: str
    school_name: str
    metrics: List[TeamProfileMetric] = Field(default_factory=list)


class TeamMatchOut(BaseModel):
    game_id: int
    region: str
    round_no: int = 0
    opponent: str
    camp: str
    winner: str
    duration: int
    started_at: str = ""
    won: bool


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------
class MatchOut(BaseModel):
    game_id: int
    region: str
    match_no: int = 0
    round_no: int = 0
    red_school: str
    blue_school: str
    winner: str
    duration: int
    started_at: str = ""
    red_team_id: str = ""
    blue_team_id: str = ""


class EventOut(BaseModel):
    t: float
    etype: str
    robot_id: int
    rtype: str = ""
    camp: str = ""
    school: str = ""
    target_id: Optional[int] = None
    target_type: str = ""
    category: str = ""
    value: Optional[float] = None
    note: str = ""


class RobotStateOut(BaseModel):
    robot_id: int
    rtype: str
    camp: str
    school: str = ""
    x: float
    y: float
    z: float = 0.0
    hp: float
    maxhp: float
    yaw: float
    yaw_ok: bool = True
    alive: bool = True
    known: bool = True
    ammo17: float = 0.0
    heat17: float = 0.0
    vuln: bool = False
    power: float = 0.0


class MatchStateOut(BaseModel):
    game_id: int
    t: float
    duration: int
    robots: List[RobotStateOut] = Field(default_factory=list)
    buildings: List[RobotStateOut] = Field(default_factory=list)


class MatchStatesOut(BaseModel):
    """Full per-second state series for one match, compact enough for the
    frontend to preload and animate locally (1 Hz raw data, interpolated
    in the browser)."""
    game_id: int
    duration: int
    step: int = 1
    states: List[MatchStateOut] = Field(default_factory=list)


class TimelinePoint(BaseModel):
    t: float
    events: List[str] = Field(default_factory=list)


class MatchTimelineOut(BaseModel):
    game_id: int
    duration: int
    points: List[TimelinePoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
class HeatmapCell(BaseModel):
    x: int
    y: int
    count: float = 0.0
    density: float = 0.0


class HeatmapOut(BaseModel):
    team_id: str = ""
    rtype: str = ""
    phase: str = ""
    nx: int
    ny: int
    cell_m: float = 1.0
    cells: List[HeatmapCell] = Field(default_factory=list)
    n: int = 0
    n_matches: int = 0
    reliable: bool = True
    note: str = ""


class FlowCell(BaseModel):
    x: int
    y: int
    mean_dx: float = 0.0
    mean_dy: float = 0.0
    speed: float = 0.0
    n: int = 0
    enter_dir: float = 0.0
    leave_dir: float = 0.0
    stay_time: float = 0.0
    common_next: Optional[List[int]] = None


class FlowOut(BaseModel):
    team_id: str = ""
    rtype: str = ""
    phase: str = ""
    nx: int
    ny: int
    cell_m: float = 1.0
    cells: List[FlowCell] = Field(default_factory=list)
    n: int = 0
    n_matches: int = 0


class FormationPoint(BaseModel):
    t: float
    centroid_x: float
    centroid_y: float
    width: float
    depth: float
    spacing: float
    front_robot: str = ""
    back_robot: str = ""
    area: float = 0.0
    concentration: float = 0.0


class FormationOut(BaseModel):
    game_id: int
    camp: str
    points: List[FormationPoint] = Field(default_factory=list)


class BehaviorCase(BaseModel):
    game_id: int
    t: float
    opponent: str = ""
    bvid: str = ""
    video_url: str = ""
    video_time: Optional[float] = None
    aligned: bool = False
    robot_id: int = 0
    rtype: str = ""
    detail: str = ""


class EventBehaviorOut(BaseModel):
    event: str
    team_id: str = ""
    horizon_s: int = 15
    behaviors: Dict[str, float] = Field(default_factory=dict)
    n: int = 0
    n_matches: int = 0
    cases: List[BehaviorCase] = Field(default_factory=list)


class MatchupOut(BaseModel):
    team_a: str
    team_b: str
    matches: List[MatchOut] = Field(default_factory=list)
    first_contact: Dict[str, Any] = Field(default_factory=dict)
    overlap: List[HeatmapCell] = Field(default_factory=list)
    a_heat: List[HeatmapCell] = Field(default_factory=list)
    b_heat: List[HeatmapCell] = Field(default_factory=list)
    nx: int = 28
    ny: int = 15
    cell_m: float = 1.0
    n: int = 0
    n_matches: int = 0
    note: str = ""


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------
class VideoOut(BaseModel):
    id: int
    game_id: int
    platform: str = "bilibili"
    bvid: str = ""
    url: str = ""
    title: str = ""
    offset: Optional[float] = None
    alignment_status: str = "uncalibrated"
    anchors: List[Dict[str, Any]] = Field(default_factory=list)


class VideoLibraryIn(BaseModel):
    platform: str = "bilibili"
    bvid: str = ""
    url: str = ""
    title: str = ""
    note: str = ""


class VideoLibraryOut(BaseModel):
    id: int
    platform: str = "bilibili"
    bvid: str = ""
    url: str = ""
    title: str = ""
    note: str = ""


class VideoIn(BaseModel):
    game_id: int
    platform: str = "bilibili"
    bvid: str = ""
    url: str = ""
    title: str = ""
    offset: Optional[float] = None


class AnchorIn(BaseModel):
    game_time: float
    video_time: float
    confidence: float = 0.5


class AnchorOut(BaseModel):
    id: int
    match_video_id: int
    game_time: float
    video_time: float
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# RL inference
# ---------------------------------------------------------------------------
class InferenceRequest(BaseModel):
    game_id: int
    t: float
    camp: str = "红"
    rtype: str = "步兵3"
    run: str = "rm_runs/infantry_iql_tactical"
    algo: str = "iql"


class InferenceOut(BaseModel):
    game_id: int
    t: float
    algo: str
    goal_dx: float = 0.0
    goal_dy: float = 0.0
    fire: bool = False
    p_fire: float = 0.0
    target: Optional[int] = None
    target_label: str = ""
    target_conf: float = 0.0
    target_probs: List[float] = Field(default_factory=list)
    human: Dict[str, Any] = Field(default_factory=dict)
    agree: Dict[str, Any] = Field(default_factory=dict)


class DisagreementItem(BaseModel):
    game_id: int
    t: float
    score: float
    rtype: str
    camp: str
    ai: Dict[str, Any] = Field(default_factory=dict)
    human: Dict[str, Any] = Field(default_factory=dict)


class DisagreementOut(BaseModel):
    model: str
    items: List[DisagreementItem] = Field(default_factory=list)
    note: str = ""


class DisagreementOut(BaseModel):
    game_id: int
    t: float
    score: float
    target_disagree: bool = False
    fire_disagree: bool = False
    nav_cos: float = 0.0
    rtype: str = ""
    camp: str = ""


class SimilarStateOut(BaseModel):
    game_id: int
    t: float
    similarity: float
    opponent: str = ""
    future: List[Dict[str, Any]] = Field(default_factory=list)
    bvid: str = ""
    video_time: Optional[float] = None


class BriefSection(BaseModel):
    title: str
    findings: List[str] = Field(default_factory=list)
    suggestion: str = ""
    n: int = 0
    n_matches: int = 0


class TacticalBriefOut(BaseModel):
    team_id: str
    school_name: str
    generated_at: str = ""
    sections: List[BriefSection] = Field(default_factory=list)
    reliable: bool = True


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------
class ErrorOut(BaseModel):
    detail: str
