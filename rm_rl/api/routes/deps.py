"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Request

from ...tactical.analytics import TacticalStore
from ...tactical.meta import MetaStore
from ...tactical.team_identity import TeamIdentity


class State:
    def __init__(self, store: TacticalStore, meta: MetaStore,
                 identity: TeamIdentity):
        self.store = store
        self.meta = meta
        self.identity = identity


def get_state(request: Request) -> State:
    return request.app.state.state
