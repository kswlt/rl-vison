"""Video association endpoints (Bilibili-first).

We store only metadata (URL / BVID / anchors), never the media.  The frontend
drives the platform timeline and asks the Bilibili iframe to seek — the
platform timeline stays authoritative because cross-origin iframe reads are
unreliable.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ...tactical.schemas import (AnchorIn, AnchorOut, VideoIn,
                                 VideoLibraryIn, VideoLibraryOut, VideoOut)
from .deps import get_state

router = APIRouter(tags=["videos"])


# -- video library -----------------------------------------------------------
@router.get("/videos/library", response_model=list[VideoLibraryOut])
def library_list(state=Depends(get_state)):
    return state.meta.library_list()


@router.post("/videos/library", response_model=VideoLibraryOut)
def library_add(v: VideoLibraryIn, state=Depends(get_state)):
    if not v.bvid and not v.url:
        raise HTTPException(422, "bvid or url required")
    return state.meta.library_add(v)


@router.post("/videos/library/{lib_id}/associate", response_model=VideoOut)
def library_associate(lib_id: int, game_id: int, state=Depends(get_state)):
    """Move a library video onto a real match (only if that game exists)."""
    lib = state.meta.library_video(lib_id)
    if lib is None:
        raise HTTPException(404, f"library video {lib_id} not found")
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    return state.meta.add_video(VideoIn(
        game_id=game_id, platform=lib.platform, bvid=lib.bvid, url=lib.url,
        title=lib.title))


@router.get("/videos/{game_id}", response_model=list[VideoOut])
def videos_for_game(game_id: int, state=Depends(get_state)):
    if state.store.match(game_id) is None:
        raise HTTPException(404, f"game_id {game_id} not found")
    return state.meta.videos_for_game(game_id)


@router.post("/videos", response_model=VideoOut)
def add_video(v: VideoIn, state=Depends(get_state)):
    if state.store.match(v.game_id) is None:
        raise HTTPException(404, f"game_id {v.game_id} not found")
    return state.meta.add_video(v)


@router.post("/videos/{video_id}/anchors", response_model=AnchorOut)
def add_anchor(video_id: int, a: AnchorIn, state=Depends(get_state)):
    if state.meta.video(video_id) is None:
        raise HTTPException(404, f"video {video_id} not found")
    return state.meta.add_anchor(video_id, a)


@router.get("/videos/{video_id}/map", response_model=dict)
def map_time(video_id: int, video_time: float, state=Depends(get_state)):
    """video_time -> game_time using piecewise anchors (or simple offset)."""
    if state.meta.video(video_id) is None:
        raise HTTPException(404, f"video {video_id} not found")
    gt = state.meta.video_to_game(video_id, video_time)
    return dict(video_id=video_id, video_time=video_time, game_time=gt)


@router.get("/videos/{video_id}/inverse", response_model=dict)
def map_time_inverse(video_id: int, game_time: float, state=Depends(get_state)):
    """game_time -> video_time (platform timeline -> B站 seek target)."""
    if state.meta.video(video_id) is None:
        raise HTTPException(404, f"video {video_id} not found")
    vt = state.meta.game_to_video(video_id, game_time)
    return dict(video_id=video_id, game_time=game_time, video_time=vt)
