"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fastapi import Request

from ...tactical.analytics import TacticalStore
from ...tactical.cache import get_or_compute as _get_or_compute
from ...tactical.meta import MetaStore
from ...tactical.team_identity import TeamIdentity


class State:
    def __init__(self, store: TacticalStore, meta: MetaStore,
                 identity: TeamIdentity, rl=None):
        self.store = store
        self.meta = meta
        self.identity = identity
        self.rl = rl

    def cached(self, kind: str, params: Dict[str, Any],
               compute: Callable[[], Any], ttl_s: Optional[float] = None):
        """Disk-cached aggregate computation, keyed by params + DB signature."""
        return _get_or_compute(self.store.db_path, kind, params, compute,
                               ttl_s=ttl_s)


def get_state(request: Request) -> State:
    return request.app.state.state
