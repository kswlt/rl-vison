"""Shared fixtures: a small synthetic referee database.

Tests must never depend on the 1.18 GB official dataset, so this builds a tiny
two-match league with scripted trajectories:

  match 1: 测试大学A (红) vs 测试大学B (蓝), 60 s
  match 2: 测试大学A (蓝) vs 测试大学B (红), 60 s

The red infantry3 of match 1 walks in a straight line from the red corner
toward the centre; the blue outpost loses HP mid-game so outpost conditions
have something to bite on.
"""
from __future__ import annotations

import os
import sqlite3

import numpy as np
import pytest

from rm_rl.tactical.analytics import TacticalStore
from rm_rl.tactical.meta import MetaStore

SCHOOL_A = "测试大学A"
SCHOOL_B = "测试大学B"

MOBILE = [1, 2, 3, 4, 6, 7]          # red base ids (blue = +100)
BUILD = [10, 11]                      # base, outpost


def _make_db(path: str):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("""CREATE TABLE matches (
        "赛区" TEXT, "场次号" INT, "赛程" TEXT, "局号" INT, game_id INT,
        web_game_id INT, "红方学校" TEXT, "蓝方学校" TEXT, "胜方" TEXT,
        "开始时间" TEXT, "时长秒" INT)""")
    cur.execute("""CREATE TABLE timeseries (
        "赛区" TEXT, "场次号" INT, "赛程" TEXT, "局号" INT, game_id INT,
        "时刻秒" REAL, robot_id INT, "机器人类型" TEXT, "阵营" TEXT,
        "学校名" TEXT, "对手学校" TEXT, "当前血量" REAL, "最大血量" REAL,
        x REAL, y REAL, z REAL, "枪口朝向" REAL, "底盘功率" REAL,
        "小热量" REAL, "小热量上限" REAL, "大热量" REAL, "大热量上限" REAL,
        "累计17mm发弹" REAL, "累计42mm发弹" REAL, "队伍总金币" REAL,
        "队伍剩余金币" REAL, "是否易伤" INT)""")
    cur.execute("""CREATE TABLE events (
        "赛区" TEXT, "场次号" INT, "赛程" TEXT, "局号" INT, game_id INT,
        "时刻秒" REAL, "事件类型" TEXT, robot_id INT, "机器人类型" TEXT,
        "阵营" TEXT, "学校名" TEXT, "目标robot_id" INT, "目标类型" TEXT,
        "类别" TEXT, "数值" REAL, "备注" TEXT)""")

    # matches
    cur.execute("INSERT INTO matches VALUES "
                "('东部赛区',1,'【东部赛区】第1场',1,1001,1,?,?,?,?,60)",
                (SCHOOL_A, SCHOOL_B, "红", "2026-05-21 08:00:00"))
    cur.execute("INSERT INTO matches VALUES "
                "('东部赛区',2,'【东部赛区】第2场',1,1002,2,?,?,?,?,60)",
                (SCHOOL_B, SCHOOL_A, "蓝", "2026-05-21 09:00:00"))

    _fill_game(cur, gid=1001, red_school=SCHOOL_A, blue_school=SCHOOL_B,
               outpost_camp="蓝", outpost_hp_drop_t=40)
    _fill_game(cur, gid=1002, red_school=SCHOOL_B, blue_school=SCHOOL_A,
               outpost_camp="蓝", outpost_hp_drop_t=30)
    con.commit()
    con.close()


def _fill_game(cur, gid, red_school, blue_school, outpost_camp, outpost_hp_drop_t):
    T = 60
    for camp, school, base in (("红", red_school, 0), ("蓝", blue_school, 100)):
        opp = blue_school if camp == "红" else red_school
        for rid0 in MOBILE + BUILD:
            rid = rid0 + base
            rtype = {1: "英雄", 2: "工程", 3: "步兵3", 4: "步兵4", 6: "空中",
                     7: "哨兵", 10: "基地", 11: "前哨站"}[rid0]
            maxhp = {"英雄": 450.0, "工程": 250.0, "步兵3": 400.0,
                     "步兵4": 400.0, "空中": 100.0, "哨兵": 400.0,
                     "基地": 5000.0, "前哨站": 1500.0}[rtype]
            for t in range(1, T + 1):
                # scripted motion: red walks +x, blue walks -x (raw frame)
                if rid0 == 3 and camp == "红":
                    x = 2.0 + t * 0.2
                    y = 7.5
                    hp = maxhp
                elif rid0 == 3 and camp == "蓝":
                    x = 26.0 - t * 0.2
                    y = 7.5
                    hp = maxhp
                else:
                    x = 2.0 if camp == "红" else 26.0
                    y = 7.5
                    hp = maxhp
                if rid0 == 11:      # outpost
                    x, y = 1.0, 1.0 if camp == "红" else 27.0
                    hp = maxhp
                    if camp == outpost_camp and t >= outpost_hp_drop_t:
                        hp = maxhp * 0.4
                if rid0 == 10:      # base
                    x, y = 1.0, 1.0 if camp == "红" else 27.0
                    hp = maxhp
                alive = 1
                ammo = 5.0 if t >= 10 else 0.0
                cur.execute(
                    "INSERT INTO timeseries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,"
                    "?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("东部赛区", 1, "【东部赛区】第1场", 1, gid, float(t), rid,
                     rtype, camp, school, opp, hp, maxhp, x, y, 0.5,
                     -48.0 if rid0 in (1, 3, 4, 6, 7) else -140.0,
                     20.0, 0.0, 100.0, 0.0, 100.0, ammo, 0.0, 500.0, 400.0, 0))
    # a hit event on the outpost of ``outpost_camp`` (owner is the victim)
    victim_school = blue_school if outpost_camp == "蓝" else red_school
    shooter_school = red_school if outpost_camp == "蓝" else blue_school
    cur.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("东部赛区", 1, "【东部赛区】第1场", 1, gid, float(outpost_hp_drop_t),
                 "受击", 111 if outpost_camp == "蓝" else 11, "前哨站",
                 outpost_camp, victim_school, None, "前哨站", "17mm",
                 300.0, ""))


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("tactical") / "synth.sqlite")
    _make_db(path)
    return path


@pytest.fixture(scope="session")
def store(db_path):
    return TacticalStore(db_path)


@pytest.fixture(scope="session")
def meta(db_path, tmp_path_factory):
    return MetaStore(str(tmp_path_factory.mktemp("meta") / "meta.sqlite"))


@pytest.fixture(scope="session")
def client(db_path, tmp_path_factory):
    from fastapi.testclient import TestClient
    from rm_rl.api.app import create_app
    meta_path = str(tmp_path_factory.mktemp("meta") / "meta.sqlite")
    app = create_app(db_path=db_path, meta_path=meta_path)
    return TestClient(app)
