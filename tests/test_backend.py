"""Backend tests: team normalisation, conditions, timeline, formation,
event response, video alignment, API surface."""
from __future__ import annotations


# ---------------------------------------------------------------------------
# team normalisation
# ---------------------------------------------------------------------------
def test_team_identity_resolves_aliases(store):
    from rm_rl.tactical.team_identity import TeamIdentity
    ti = TeamIdentity(schools=["测试大学A", "测试大学B"])
    ti.add_schools(["测试大学A", "测试大学B"])
    assert ti.resolve("测试大学A") == "测试大学A"
    assert ti.resolve("广东工业大学") == "广东工业大学"
    assert ti.resolve("DynamicX") == "广东工业大学"
    assert ti.resolve("广工") == "广东工业大学"
    assert ti.resolve("不存在的学校") is None


def test_team_api_lists_teams(client):
    r = client.get("/api/teams")
    assert r.status_code == 200
    names = [t["school_name"] for t in r.json()]
    assert "测试大学A" in names


# ---------------------------------------------------------------------------
# conditions
# ---------------------------------------------------------------------------
def test_condition_phase_and_outpost(store):
    from rm_rl.tactical.conditions import Condition, mask_seconds
    game = store.game(1001)
    seconds = store.seconds(1001)
    # outpost < 50% after t=40 for camp 蓝 in match 1
    mask = mask_seconds(Condition(outpost="lt50", camp="蓝"), game, seconds)
    assert any(v for t, v in mask.items() if t >= 40)
    assert not any(v for t, v in mask.items() if t < 35)
    # open30 phase
    mask2 = mask_seconds(Condition(phase="open30", camp="红"), game, seconds)
    assert all(t <= 30 for t, v in mask2.items() if v)


def test_conditional_heatmap(store):
    from rm_rl.tactical.analytics import occupancy_heatmap
    from rm_rl.tactical.conditions import Condition
    out = occupancy_heatmap(store, Condition(), school="测试大学A")
    assert out.n > 0
    assert out.n_matches == 2
    # red infantry3 walks +x from x=2 -> cells along the row
    cells = {(c.x, c.y): c for c in out.cells}
    assert (2, 7) in cells  # 1 m grid, x in [2,3)


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------
def test_timeline_endpoint(client):
    r = client.get("/api/matches/1001/timeline")
    assert r.status_code == 200
    data = r.json()
    assert data["duration"] == 60
    assert len(data["points"]) == 60


def test_state_endpoint(client):
    r = client.get("/api/matches/1001/state", params={"t": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["t"] == 20
    ids = [rb["robot_id"] for rb in data["robots"]]
    assert 3 in ids and 103 in ids


# ---------------------------------------------------------------------------
# formation
# ---------------------------------------------------------------------------
def test_formation_series(store):
    from rm_rl.tactical.formations import formation_series
    out = formation_series(store, 1001, "红", step=5)
    assert len(out.points) >= 1
    p = out.points[0]
    assert p.centroid_x >= 0 and p.width >= 0


# ---------------------------------------------------------------------------
# event response
# ---------------------------------------------------------------------------
def test_event_response(store):
    from rm_rl.tactical import events as EV
    res = EV.event_response(store, "测试大学A", rtype="步兵3")
    kinds = {o.event for o in res}
    assert "outpost_lt50" in kinds
    er = next(o for o in res if o.event == "outpost_lt50")
    assert er.n >= 1 and er.n_matches >= 1
    assert sum(er.behaviors.values()) > 99.0


# ---------------------------------------------------------------------------
# video alignment
# ---------------------------------------------------------------------------
def test_video_offset(meta):
    from rm_rl.tactical.schemas import VideoIn
    v = meta.add_video(VideoIn(game_id=1001, bvid="BV1xx", url="https://bili",
                               title="t", offset=222.0))
    assert v.alignment_status == "calibrated"
    assert meta.game_to_video(v.id, 100.0) == 322.0
    assert meta.video_to_game(v.id, 322.0) == 100.0


def test_piecewise_alignment(meta):
    from rm_rl.tactical.schemas import AnchorIn, VideoIn
    v = meta.add_video(VideoIn(game_id=1001, bvid="BV2xx", url="https://bili",
                               title="t"))
    meta.add_anchor(v.id, AnchorIn(game_time=0, video_time=222, confidence=0.9))
    meta.add_anchor(v.id, AnchorIn(game_time=180, video_time=405, confidence=0.8))
    meta.add_anchor(v.id, AnchorIn(game_time=360, video_time=591, confidence=0.8))
    # midpoint of the first segment
    gt = meta.video_to_game(v.id, 222 + (405 - 222) / 2)
    assert abs(gt - 90.0) < 1e-6
    vt = meta.game_to_video(v.id, 90.0)
    assert abs(vt - (222 + (405 - 222) / 2)) < 1e-6


def test_video_library(client):
    r = client.post("/api/videos/library", json=dict(
        platform="bilibili", bvid="BV18Tup6uEg5",
        url="https://www.bilibili.com/video/BV18Tup6uEg5/",
        title="全国赛 第五十三场", note="demo"))
    assert r.status_code == 200
    lib_id = r.json()["id"]
    r2 = client.get("/api/videos/library")
    assert r2.status_code == 200
    assert any(v["id"] == lib_id for v in r2.json())
    # associate onto a real game in the fixture DB
    r3 = client.post(f"/api/videos/library/{lib_id}/associate",
                     params={"game_id": 1001})
    assert r3.status_code == 200
    assert r3.json()["game_id"] == 1001
    # associating onto a non-existent game is rejected
    r4 = client.post(f"/api/videos/library/{lib_id}/associate",
                     params={"game_id": 999999})
    assert r4.status_code == 404


def test_video_api(client):
    r = client.post("/api/videos", json=dict(
        game_id=1002, platform="bilibili", bvid="BV18Tup6uEg5",
        url="https://www.bilibili.com/video/BV18Tup6uEg5/",
        title="全国赛 第五十三场", offset=222))
    assert r.status_code == 200
    vid = r.json()["id"]
    r2 = client.get("/api/videos/1002")
    assert r2.status_code == 200 and len(r2.json()) == 1
    r3 = client.post(f"/api/videos/{vid}/anchors", json=dict(
        game_time=180, video_time=405, confidence=0.9))
    assert r3.status_code == 200
    r4 = client.get(f"/api/videos/{vid}/inverse", params={"game_time": 180})
    assert abs(r4.json()["video_time"] - 405.0) < 1e-6


# ---------------------------------------------------------------------------
# matchup
# ---------------------------------------------------------------------------
def test_matchup_endpoint(client):
    r = client.get("/api/analytics/matchup",
                   params={"team_a": "测试大学A", "team_b": "测试大学B"})
    assert r.status_code == 200
    data = r.json()
    assert data["n_matches"] >= 1
    assert data["a_heat"] and data["b_heat"]
    assert "note" in data and "历史" in data["note"]
    assert data["first_contact"]["n"] >= 0


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unknown_team_404(client):
    r = client.get("/api/teams/不存在的学校/profile")
    assert r.status_code == 404


def test_analytics_endpoints(client):
    for path in ("/api/analytics/heatmap?team=测试大学A",
                 "/api/analytics/flow?team=测试大学A"):
        r = client.get(path)
        assert r.status_code == 200, path
    r = client.get("/api/analytics/formation", params={"game_id": 1001})
    assert r.status_code == 200
    r = client.get("/api/analytics/event-response", params={"team": "测试大学A"})
    assert r.status_code == 200


def test_team_profile(client):
    r = client.get("/api/teams/测试大学A/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["team_id"] == "测试大学A"
    keys = {m["key"] for m in data["metrics"]}
    assert "aggression" in keys and "front_occupancy" in keys
