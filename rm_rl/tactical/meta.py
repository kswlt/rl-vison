"""Meta store: team identity cache, match videos and alignment anchors.

The referee database is read-only; anything the *platform* adds (video links,
alignment anchors, curated aliases) lives in a small separate SQLite file
(``data/tactical_meta.sqlite`` by default).  This keeps the authoritative
dataset untouched and makes the whole meta layer easy to back up / reset.

Bilibili policy (per requirements): we store only URL / BVID / title / offset /
anchors — never the video itself, never a downloaded copy.
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Dict, List, Optional

from .schemas import AnchorIn, AnchorOut, VideoIn, VideoOut

SCHEMA = """
CREATE TABLE IF NOT EXISTS match_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    platform TEXT NOT NULL DEFAULT 'bilibili',
    bvid TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    offset REAL,
    alignment_status TEXT NOT NULL DEFAULT 'uncalibrated',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS video_alignment_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_video_id INTEGER NOT NULL,
    game_time REAL NOT NULL,
    video_time REAL NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_mv_game ON match_videos(game_id);
CREATE INDEX IF NOT EXISTS idx_vap_video ON video_alignment_points(match_video_id);
"""


class MetaStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        con = sqlite3.connect(path)
        con.executescript(SCHEMA)
        con.commit()
        con.close()

    def _con(self):
        return sqlite3.connect(self.path)

    # -- videos -------------------------------------------------------------
    def add_video(self, v: VideoIn) -> VideoOut:
        con = self._con()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO match_videos (game_id, platform, bvid, url, title, "
            "offset, alignment_status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (v.game_id, v.platform, v.bvid, v.url, v.title, v.offset,
             "calibrated" if v.offset is not None else "uncalibrated",
             time.time()))
        vid = cur.lastrowid
        con.commit()
        out = self._row_to_video(cur.execute(
            "SELECT * FROM match_videos WHERE id=?", (vid,)).fetchone())
        con.close()
        return out

    def videos_for_game(self, game_id: int) -> List[VideoOut]:
        con = self._con()
        rows = con.execute("SELECT * FROM match_videos WHERE game_id=? "
                           "ORDER BY id", (int(game_id),)).fetchall()
        out = [self._row_to_video(r) for r in rows]
        con.close()
        return out

    def video(self, video_id: int) -> Optional[VideoOut]:
        con = self._con()
        r = con.execute("SELECT * FROM match_videos WHERE id=?",
                        (int(video_id),)).fetchone()
        out = self._row_to_video(r) if r else None
        con.close()
        return out

    @staticmethod
    def _row_to_video(r) -> VideoOut:
        (vid, game_id, platform, bvid, url, title, offset,
         status, created) = r
        return VideoOut(id=vid, game_id=game_id, platform=platform,
                        bvid=bvid, url=url, title=title, offset=offset,
                        alignment_status=status)

    # -- anchors ------------------------------------------------------------
    def add_anchor(self, video_id: int, a: AnchorIn) -> AnchorOut:
        con = self._con()
        cur = con.cursor()
        cur.execute("INSERT INTO video_alignment_points "
                    "(match_video_id, game_time, video_time, confidence) "
                    "VALUES (?,?,?,?)",
                    (int(video_id), a.game_time, a.video_time, a.confidence))
        aid = cur.lastrowid
        if a.game_time == 0.0:
            # first anchor at game t=0 defines the simple offset
            cur.execute("UPDATE match_videos SET offset=?, "
                        "alignment_status='calibrated' WHERE id=?",
                        (a.video_time, int(video_id)))
        else:
            cur.execute("UPDATE match_videos SET alignment_status='calibrated' "
                        "WHERE id=?", (int(video_id),))
        con.commit()
        out = AnchorOut(id=aid, match_video_id=int(video_id),
                        game_time=a.game_time, video_time=a.video_time,
                        confidence=a.confidence)
        con.close()
        return out

    def anchors_for(self, video_id: int) -> List[AnchorOut]:
        con = self._con()
        rows = con.execute("SELECT id, match_video_id, game_time, video_time, "
                           "confidence FROM video_alignment_points "
                           "WHERE match_video_id=? ORDER BY game_time",
                           (int(video_id),)).fetchall()
        out = [AnchorOut(id=r[0], match_video_id=r[1], game_time=r[2],
                         video_time=r[3], confidence=r[4]) for r in rows]
        con.close()
        return out

    def video_to_game(self, video_id: int, video_time: float) -> Optional[float]:
        """Map a video time to a game time using piecewise-linear anchors."""
        anchors = self.anchors_for(video_id)
        if not anchors:
            v = self.video(video_id)
            if v and v.offset is not None:
                return video_time - v.offset
            return None
        anchors.sort(key=lambda a: a.video_time)
        if len(anchors) == 1:
            a = anchors[0]
            return a.game_time + (video_time - a.video_time)
        for i in range(len(anchors) - 1):
            a0, a1 = anchors[i], anchors[i + 1]
            if a0.video_time <= video_time <= a1.video_time:
                span = max(a1.video_time - a0.video_time, 1e-6)
                w = (video_time - a0.video_time) / span
                return a0.game_time + w * (a1.game_time - a0.game_time)
        if video_time < anchors[0].video_time:
            a = anchors[0]
            return a.game_time + (video_time - a.video_time)
        a = anchors[-1]
        return a.game_time + (video_time - a.video_time)

    def game_to_video(self, video_id: int, game_time: float) -> Optional[float]:
        """Inverse mapping: game time -> video time (platform timeline drives)."""
        anchors = self.anchors_for(video_id)
        if not anchors:
            v = self.video(video_id)
            if v and v.offset is not None:
                return game_time + v.offset
            return None
        anchors.sort(key=lambda a: a.game_time)
        if len(anchors) == 1:
            a = anchors[0]
            return a.video_time + (game_time - a.game_time)
        for i in range(len(anchors) - 1):
            a0, a1 = anchors[i], anchors[i + 1]
            if a0.game_time <= game_time <= a1.game_time:
                span = max(a1.game_time - a0.game_time, 1e-6)
                w = (game_time - a0.game_time) / span
                return a0.video_time + w * (a1.video_time - a0.video_time)
        if game_time < anchors[0].game_time:
            a = anchors[0]
            return a.video_time + (game_time - a.game_time)
        a = anchors[-1]
        return a.video_time + (game_time - a.game_time)
