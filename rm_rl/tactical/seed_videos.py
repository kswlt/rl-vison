"""Seed the video library with the real national-final match the user gave.

全国赛 第五十三场 上海交通大学 交龙战队 VS 广东工业大学 DynamicX战队
BVID: BV18Tup6uEg5  URL: https://www.bilibili.com/video/BV18Tup6uEg5/

This match is NOT in the 2026 regional dataset (613 matches), so it stays in
the *video library* (no fake game_id, no fake time sync).  Once a matching
game exists in the database you can associate it via
``POST /api/videos/library/{id}/associate?game_id=`` — only real games are
accepted.  Run ``python -m rm_rl.tactical.seed_videos`` (idempotent).
"""
from __future__ import annotations

import os

from .meta import MetaStore
from .schemas import VideoLibraryIn

DEFAULT_META = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "data", "tactical_meta.sqlite")

SEEDS = [
    VideoLibraryIn(
        platform="bilibili",
        bvid="BV18Tup6uEg5",
        url="https://www.bilibili.com/video/BV18Tup6uEg5/",
        title="全国赛 第五十三场 上海交通大学 交龙战队 VS 广东工业大学 DynamicX战队",
        note="全国赛不在 2026 区域赛数据集，无逐秒数据，仅作视频库演示；"
             "数据库找到对应比赛后可手动关联。",
    ),
]


def main(meta_path: str = DEFAULT_META) -> int:
    meta = MetaStore(meta_path)
    added = 0
    existing = {v.bvid for v in meta.library_list()}
    for seed in SEEDS:
        if seed.bvid in existing:
            continue
        meta.library_add(seed)
        added += 1
        print(f"seeded library video: {seed.title} ({seed.bvid})")
    if added == 0:
        print("video library already seeded (idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
