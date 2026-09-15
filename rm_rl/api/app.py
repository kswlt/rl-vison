"""FastAPI application factory and shared app state.

Run:
    python -m rm_rl.api.app                 # dev, http://localhost:8000/docs
    python scripts/run_tactical_dashboard.py  # one-command launcher (later)

When ``web/dist`` exists (production build) the app also serves the React
frontend, so the final user needs only one process.
"""
from __future__ import annotations

import argparse
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..tactical.analytics import TacticalStore
from ..tactical.cache import get_or_compute as _get_or_compute
from ..tactical.meta import MetaStore
from ..tactical.team_identity import TeamIdentity, build_team_identity_from_db
from .routes import analytics, inference, matches, teams, videos

DEFAULT_DB = os.path.join("dataset", "rmuc_2026_region_dataset.sqlite")
DEFAULT_META = os.path.join("data", "tactical_meta.sqlite")
DEFAULT_IDENTITY = os.path.join("data", "team_identity.json")
WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "web", "dist")


class AppState:
    """Shared services, attached to ``app.state.state``."""

    def __init__(self, db_path: str, meta_path: str, identity_path: str):
        self.db_path = db_path
        self.store = TacticalStore(db_path)
        self.meta = MetaStore(meta_path)
        fresh = build_team_identity_from_db(db_path)
        self.identity = fresh
        if os.path.exists(identity_path):
            try:
                self.identity = TeamIdentity.load(identity_path,
                                                  expect_signature=fresh.signature())
            except (ValueError, KeyError):
                self.identity = fresh
        try:
            self.identity.save(identity_path)
        except OSError:
            pass

    def cached(self, kind: str, params: dict, compute, ttl_s=None):
        return _get_or_compute(self.db_path, kind, params, compute, ttl_s=ttl_s)


def create_app(db_path: str = DEFAULT_DB, meta_path: str = DEFAULT_META,
               identity_path: str = DEFAULT_IDENTITY) -> FastAPI:
    app = FastAPI(
        title="RMUC Tactical Intelligence",
        description="Dynamic tactical intelligence, opponent research, AI "
                    "decision support and replay review for RMUC.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # dev; tighten for production deploys
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    state = AppState(db_path, meta_path, identity_path)
    app.state.state = state

    app.include_router(teams.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(videos.router, prefix="/api")
    app.include_router(inference.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return dict(status="ok", db=os.path.basename(db_path),
                    matches=int(len(state.store.matches())))

    # serve the production React build if present
    if os.path.isdir(WEB_DIST):
        app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIST, "assets")),
                  name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            candidate = os.path.join(WEB_DIST, full_path)
            if full_path and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(WEB_DIST, "index.html"))
    return app


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--meta", default=DEFAULT_META)
    ap.add_argument("--identity", default=DEFAULT_IDENTITY)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    import uvicorn
    app = create_app(args.db, args.meta, args.identity)
    print(f"[tactical] serving on http://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
