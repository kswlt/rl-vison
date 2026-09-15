"""Tactical RL inference service.

Wraps the project's *existing* offline-RL stack (feature builder + deployment
wrapper) so the web platform can answer:

  * what would the BC / IQL / Decision Transformer policy do at (game, t) for a
    given robot?  (moving goal, fire permission, soft target distribution)
  * how far is that from what the human actually did?

It deliberately reuses ``rm_rl.data.build_dataset.load_game_arrays`` +
``rm_rl.data.features.build_obs`` + ``rm_rl.deploy.load_policy / decode_action``
— the observation goes through the full constructor (allied / enemy relative
positions, distances, bearings, vis_map engagement prior, team prior), never a
hand-rolled subset.  If no checkpoint exists the API stays honest and reports
"model not loaded".
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np

from ..data import build_dataset as BD
from ..data import features as F
from ..data import schema as S
from ..data.team_prior import TeamPrior
from ..data.vis_map import VisibilityMap
from ..deploy import MLPPolicyRunner, load_policy

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIRS = {
    "bc": os.environ.get("RMUC_BC_DIR", os.path.join(REPO_ROOT, "rm_runs", "infantry_bc_tactical")),
    "iql": os.environ.get("RMUC_IQL_DIR", os.path.join(REPO_ROOT, "rm_runs", "infantry_iql_tactical")),
    "dt": os.environ.get("RMUC_DT_DIR", os.path.join(REPO_ROOT, "rm_runs", "infantry_dt_tactical")),
}
MODEL_LABELS = {"bc": "BC", "iql": "IQL", "dt": "Decision Transformer"}


def model_available(model: str) -> bool:
    d = MODEL_DIRS.get(model)
    if not d:
        return False
    return os.path.isfile(os.path.join(d, "best.pt")) or \
        os.path.isfile(os.path.join(d, "final.pt"))


class TacticalRL:
    """Lazy-loaded priors + policies; safe for long-lived app state."""

    def __init__(self, db_path: str,
                 vis_map: Optional[str] = None,
                 team_prior: Optional[str] = None,
                 t_max_ref: float = 450.0):
        self.db_path = db_path
        self.t_max_ref = t_max_ref
        self._vmap = None
        self._prior = None
        self._team_cache: Dict[str, np.ndarray] = {}
        self._runners: Dict[str, MLPPolicyRunner] = {}
        vis_map = vis_map or os.environ.get("RMUC_VIS_MAP",
                                            os.path.join(REPO_ROOT, "data", "vis_map.npz"))
        team_prior = team_prior or os.environ.get(
            "RMUC_TEAM_PRIOR", os.path.join(REPO_ROOT, "data", "team_prior.json"))
        self.vis_map_path = vis_map if os.path.isfile(vis_map) else None
        self.team_prior_path = team_prior if os.path.isfile(team_prior) else None

    # -- priors -------------------------------------------------------------
    @property
    def vmap(self) -> Optional[VisibilityMap]:
        if self._vmap is None and self.vis_map_path:
            self._vmap = VisibilityMap.load(self.vis_map_path)
        return self._vmap

    @property
    def prior(self) -> Optional[TeamPrior]:
        if self._prior is None and self.team_prior_path:
            self._prior = TeamPrior.load(self.team_prior_path)
        return self._prior

    def team_feat(self, game_id: int, camp: str) -> np.ndarray:
        key = f"{game_id}:{camp}"
        if key not in self._team_cache:
            if self.prior is None:
                self._team_cache[key] = np.zeros(TeamPrior.feats_dim(), np.float32)
            else:
                self._team_cache[key] = self.prior.feats(game_id, camp)
        return self._team_cache[key]

    # -- policy -------------------------------------------------------------
    def runner(self, model: str) -> MLPPolicyRunner:
        if model not in MODEL_DIRS:
            raise ValueError(f"unknown model {model}")
        if model not in self._runners:
            if not model_available(model):
                raise FileNotFoundError(
                    f"model not loaded: {MODEL_DIRS[model]} — run the training "
                    "pipeline (rm_rl/train) or place a checkpoint there")
            self._runners[model] = MLPPolicyRunner(MODEL_DIRS[model], device="cpu")
        return self._runners[model]

    # -- observation --------------------------------------------------------
    def obs_at(self, game_id: int, t: int, agent_type: str,
               camp: str) -> np.ndarray:
        """Full observation vector at second ``t`` for one ego robot."""
        import sqlite3
        con = sqlite3.connect(self.db_path)
        try:
            game = BD.load_game_arrays(con, game_id)
        finally:
            con.close()
        if game.T == 0:
            raise ValueError(f"game {game_id} has no data")
        t = int(np.clip(t, 1, game.T))
        obs = F.build_obs(game, camp, agent_type, t_max_ref=self.t_max_ref,
                          vis_map=self.vmap,
                          team_feat=self.team_feat(game_id, camp))
        return np.asarray(obs[t - 1], np.float32)

    def human_action(self, game_id: int, t: int, agent_type: str,
                     camp: str, action_mode: str = "tactical",
                     goal_horizon: int = 5) -> Optional[Dict]:
        """What the human actually did around second ``t`` (for disagreement)."""
        import sqlite3
        con = sqlite3.connect(self.db_path)
        try:
            game = BD.load_game_arrays(con, game_id)
        finally:
            con.close()
        if game.T == 0:
            return None
        acts = F.build_action_raw(game, camp, agent_type,
                                  action_mode=action_mode,
                                  goal_horizon=goal_horizon)
        idx = int(np.clip(t, 1, game.T - 1)) - 1
        if idx >= len(acts):
            return None
        a = acts[idx]
        ego = game.get(agent_type, camp)
        alive = bool(ego.alive[idx] > 0 and ego.alive[idx + 1] > 0)
        if not alive:
            return dict(alive=False)
        if action_mode == "tactical":
            return dict(alive=True,
                        goal_dx=float(a[0]), goal_dy=float(a[1]),
                        fire=bool(a[2] > 0.5),
                        target=int(np.argmax(a[3:])),
                        target_conf=float(a[3:].max()))
        return dict(alive=True, vx=float(a[0]), vy=float(a[1]),
                    fire=float(a[3]))

    # -- disagreement -------------------------------------------------------
    def disagreement(self, human: Optional[Dict], ai: Dict,
                     ego_xy=(0.0, 0.0)) -> float:
        """Scalar disagreement between human behaviour and the policy.

        nav: euclidean distance between normalised goal directions (dead human
        => 1.0), fire: XOR, target: 0/1 mismatch on the argmax class.  The
        returned value is in [0, ~3] — larger means the AI disagrees more.
        """
        if not human or not human.get("alive", False):
            return 1.5 if ai else 0.0
        hgx, hgy = human.get("goal_dx", 0.0), human.get("goal_dy", 0.0)
        agx, agy = ai.get("goal_dx", 0.0), ai.get("goal_dy", 0.0)
        hn = np.hypot(hgx, hgy) or 1.0
        an = np.hypot(agx, agy) or 1.0
        cos = float((hgx * agx + hgy * agy) / (hn * an))
        nav = float(np.clip(1.0 - cos, 0.0, 2.0))
        fire = 0.0 if bool(human.get("fire")) == bool(ai.get("fire")) else 1.0
        tgt = 0.0
        if human.get("target") is not None and ai.get("target") is not None:
            tgt = 0.0 if human["target"] == ai["target"] else 1.0
        return round(nav + fire + tgt, 3)
