"""RL inference endpoints.

Milestone 8 wires the real trained IQL/BC/DT checkpoints through the existing
feature builder (``rm_rl.data.features.build_obs``) and deployment wrapper
(``rm_rl.deploy``).  This module is the API surface; it reports honest
"model not loaded" errors instead of falling back to fake data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...tactical.schemas import InferenceOut
from .deps import get_state

router = APIRouter(tags=["inference"])


@router.post("/inference", response_model=InferenceOut)
def inference(req: dict, state=Depends(get_state)):
    # Placeholder until M8: report the real capability status.
    raise HTTPException(501,
                        "RL inference lands in Milestone 8; the API contract "
                        "is defined in tactical/schemas.InferenceRequest.")
