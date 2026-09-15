"""Disk-backed tactical cache.

The referee DB is the single source of truth; this cache only speeds up
repeatable aggregate queries (profile / conditional heatmap / flow field).
Every entry is keyed by the condition combination plus a database signature,
so a changed DB invalidates stale entries automatically. The UI stays honest:
cache hits and misses return the same data, and per-sample stats (n /
n_matches) are always included in the payloads themselves.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Any, Callable, Dict, Optional

from ..data import schema as S

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "tactical_cache")


def _db_signature(db_path: str) -> str:
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        n = con.execute(f'SELECT COUNT(*) FROM {S.T_MATCHES}').fetchone()[0]
        mx = con.execute(
            f'SELECT MAX("game_id") FROM {S.T_MATCHES}').fetchone()[0]
        con.close()
        return f"{n}:{mx}"
    except Exception:
        return "unknown"


def _key_path(kind: str, sig: str, params: Dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha1(f"{kind}|{sig}|{raw}".encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"{kind}_{h}.json")


def get_or_compute(db_path: str, kind: str, params: Dict[str, Any],
                   compute: Callable[[], Any],
                   ttl_s: Optional[float] = None) -> Any:
    """Return cached JSON if fresh, otherwise run ``compute`` and cache it.

    ``compute`` must return a Pydantic model or JSON-serialisable structure.
    """
    sig = _db_signature(db_path)
    path = _key_path(kind, sig, params)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    hit = False
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if ttl_s is None or time.time() - meta.get("_ts", 0) < ttl_s:
                hit = True
                data = meta.get("data")
        except Exception:
            hit = False

    if hit:
        return data

    t0 = time.time()
    data = compute()
    payload = {"_ts": time.time(), "_computed_s": round(time.time() - t0, 2),
               "data": data}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, path)
    return data


def invalidate_all(db_path: Optional[str] = None) -> int:
    """Clear the whole cache directory (used when the DB is replaced)."""
    n = 0
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(CACHE_DIR, f))
                n += 1
    return n


def cache_stats() -> Dict[str, int]:
    n = 0
    size = 0
    if os.path.isdir(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".json"):
                n += 1
                size += os.path.getsize(os.path.join(CACHE_DIR, f))
    return {"entries": n, "bytes": size}
