"""Team identity normalisation / aliases.

Video titles, forum posts and the referee database may all spell the same
school differently (广东工业大学 / DynamicX / 广工 …).  The dashboard must never
match team names by raw front-end string comparison, so every team is resolved
to a stable ``team_id`` here, on the backend.

Sources of identity:
  * the referee database's 学校名 column (authoritative for games);
  * a curated alias table shipped with the repo (video titles, short names).

Resolution order: exact alias lookup -> normalised string -> None.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
#: curated aliases: canonical school name -> list of alternate spellings
DEFAULT_ALIASES: Dict[str, List[str]] = {
    "广东工业大学": ["广东工业大学", "DynamicX", "DynamicX战队", "广工", "GDUT"],
    "上海交通大学": ["上海交通大学", "交龙", "SJTU"],
    "哈尔滨工业大学": ["哈尔滨工业大学", "哈工大", "HIT"],
    "哈尔滨工业大学（深圳）": ["哈尔滨工业大学（深圳）", "哈工大（深圳）", "哈工大深圳", "HITSZ"],
    "北京理工大学": ["北京理工大学", "北理工", "BIT"],
    "北京理工大学（珠海）": ["北京理工大学（珠海）", "北理工（珠海）"],
    "华中科技大学": ["华中科技大学", "华科", "HUST"],
    "华南理工大学": ["华南理工大学", "华工", "SCUT"],
    "电子科技大学": ["电子科技大学", "成电", "UESTC"],
    "西安交通大学": ["西安交通大学", "西交", "XJTU"],
    "浙江大学": ["浙江大学", "浙大", "ZJU"],
    "南京航空航天大学": ["南京航空航天大学", "南航", "NUAA"],
    "大连理工大学": ["大连理工大学", "大工", "DUT"],
    "东北大学": ["东北大学", "东大", "NEU"],
    "中国科学技术大学": ["中国科学技术大学", "中科大", "USTC"],
}


def normalize(name: str) -> str:
    """Lower-case, strip whitespace and CJK parens so lookups are forgiving."""
    s = str(name or "").strip().lower()
    s = re.sub(r"[（(]\s*[)）]", "", s)
    s = re.sub(r"\s+", "", s)
    return s


class TeamIdentity:
    """In-memory team registry built from the matches table + curated aliases."""

    def __init__(self, schools: Optional[List[str]] = None,
                 aliases: Optional[Dict[str, List[str]]] = None):
        self.aliases: Dict[str, str] = {}     # normalised spelling -> team_id
        self.meta: Dict[str, dict] = {}       # team_id -> metadata
        self._alias_table = aliases or DEFAULT_ALIASES
        self._schools: List[str] = []
        if schools:
            self.add_schools(schools)

    # -- construction -------------------------------------------------------
    def add_schools(self, schools: List[str]):
        seen: Dict[str, str] = {}
        for s in schools:
            if not s:
                continue
            key = normalize(s)
            if key not in seen:
                seen[key] = self._make_id(s)
        for key, tid in seen.items():
            self.aliases[key] = tid
            self.meta.setdefault(tid, dict(school_name=tid, aliases=[]))
        self._schools = sorted(seen.values())
        # curated aliases point at canonical names when those exist
        for canon, alts in self._alias_table.items():
            ck = normalize(canon)
            if ck not in self.aliases:
                self.aliases[ck] = canon
                self.meta.setdefault(canon, dict(school_name=canon, aliases=[]))
            tid = self.aliases[ck]
            meta = self.meta.setdefault(
                tid, dict(school_name=tid, aliases=[]))
            for a in alts:
                ak = normalize(a)
                self.aliases.setdefault(ak, tid)
                if a not in meta["aliases"] and a != meta.get("school_name"):
                    meta["aliases"].append(a)

    @staticmethod
    def _make_id(school: str) -> str:
        return school.strip()

    # -- queries ------------------------------------------------------------
    def resolve(self, name: str) -> Optional[str]:
        """Map any spelling to a stable team_id (None if unknown)."""
        if not name:
            return None
        return self.aliases.get(normalize(name))

    def team_name(self, team_id: str) -> str:
        meta = self.meta.get(team_id, {})
        return meta.get("school_name", team_id)

    def aliases_for(self, team_id: str) -> List[str]:
        return list(self.meta.get(team_id, {}).get("aliases", []))

    def all_team_ids(self) -> List[str]:
        return [k for k in self._schools if not k.startswith("__")]

    def to_dict(self, team_id: str) -> dict:
        return dict(
            team_id=team_id,
            school_name=self.team_name(team_id),
            team_name=None,
            aliases=self.aliases_for(team_id),
        )

    # -- persistence --------------------------------------------------------
    def signature(self) -> str:
        """Stable fingerprint of the registry's content (for cache invalidation).

        Deterministic across processes (no builtin hash, which is salted).
        """
        import hashlib
        db = self.meta.get("__signature__", {})
        db_sig = f"{db.get('db', '')}" if isinstance(db, dict) else ""
        teams = "|".join(sorted(k for k in self.meta if not k.startswith("__")))
        digest = hashlib.md5(teams.encode("utf-8")).hexdigest()[:12]
        return f"{db_sig}:{len(teams.split('|')) if teams else 0}:{digest}"

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"meta": self.meta, "aliases": self.aliases,
                       "signature": self.signature()}, f,
                      ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path: str, expect_signature: str = "") -> "TeamIdentity":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ti = cls()
        ti.meta = data.get("meta", {})
        ti.aliases = data.get("aliases", {})
        ti._schools = sorted(ti.meta.keys())
        if expect_signature and data.get("signature") != expect_signature:
            raise ValueError("team identity cache signature mismatch")
        return ti


def build_team_identity_from_db(db_path: str,
                                alias_json: Optional[str] = None) -> TeamIdentity:
    """Build the registry from the matches table (the authoritative school list)."""
    import sqlite3
    con = sqlite3.connect(db_path)
    schools = [r[0] for r in con.execute(
        'SELECT DISTINCT "红方学校" FROM matches UNION '
        'SELECT DISTINCT "蓝方学校" FROM matches')]
    n_matches = con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    con.close()
    extra = None
    if alias_json and os.path.exists(alias_json):
        with open(alias_json, "r", encoding="utf-8") as f:
            extra = json.load(f)
    ti = TeamIdentity(schools=schools, aliases=extra)
    # attach a signature that also depends on the source database so a cache
    # built from a different DB (e.g. tests) is detected and rebuilt
    ti.meta.setdefault("__signature__",
                       dict(db=f"{n_matches}:{len(schools)}"))
    return ti
