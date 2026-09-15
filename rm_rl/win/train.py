"""Train the Win Predictor (and produce calibration + metrics report).

Usage:
  python -m rm_rl.win.train
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ..data import build_dataset as BD
from ..data import features as F
from ..data import schema as S
from ..data.team_prior import TeamPrior
from ..data.vis_map import VisibilityMap
from . import dataset as D
from .predictor import WinMLP, fit_temperature, DEFAULT_DIR

REPO_ROOT = Path(__file__).resolve().parents[2]
DB = os.path.join(REPO_ROOT, "dataset", "rmuc_2026_region_dataset.sqlite")
VMAP = os.path.join(REPO_ROOT, "data", "vis_map.npz")
PRIOR = os.path.join(REPO_ROOT, "data", "team_prior.json")
AGENT = "步兵3"  # train on infantry3 (most data)


def collect_xy(game_ids, con, vmap, prior, max_per_game=120):
    """Collect obs + label for the given games (one side per timestep)."""
    xs, ys = [], []
    for gid in game_ids:
        try:
            game = BD.load_game_arrays(con, gid)
        except Exception:
            continue
        if game.T < 30:
            continue
        # red side
        for camp in (S.CAMP_RED, S.CAMP_BLUE):
            sf = prior.feats(gid, camp) if prior else np.zeros(6, np.float32)
            try:
                obs = F.build_obs(game, camp, AGENT, t_max_ref=450.0,
                                  vis_map=vmap, team_feat=sf)
            except Exception:
                continue
            # sample up to max_per_game timesteps per episode
            T = min(len(obs), game.T)
            idx = np.linspace(0, T - 1, min(max_per_game, T)).astype(int)
            label = 1.0 if D.load_win_labels(DB)[gid][camp] == "win" else 0.0
            for i in idx:
                xs.append(obs[i].astype(np.float32))
                ys.append(label)
    if not xs:
        return None, None
    return np.stack(xs), np.array(ys, dtype=np.float32)


def main():
    print("=== Win Predictor training ===")
    con = sqlite3.connect(DB)
    vmap = VisibilityMap.load(VMAP) if os.path.isfile(VMAP) else None
    prior = TeamPrior.load(PRIOR) if os.path.isfile(PRIOR) else None

    # list games
    games = list(D.iter_games(DB))
    gids = [g[0] for g in games]
    print(f"games total: {len(gids)}")

    train_g, val_g, test_g = D.game_level_split(gids)
    print(f"split: train={len(train_g)} val={len(val_g)} test={len(test_g)}")

    in_dim = F.obs_dim(AGENT)
    print(f"obs_dim = {in_dim}")

    print("collecting train...")
    Xtr, ytr = collect_xy(train_g, con, vmap, prior)
    print(f"  Xtr={Xtr.shape}  pos_rate={ytr.mean():.3f}")
    print("collecting val...")
    Xv, yv = collect_xy(val_g, con, vmap, prior)
    print(f"  Xv={Xv.shape}")
    print("collecting test...")
    Xte, yte = collect_xy(test_g, con, vmap, prior)
    print(f"  Xte={Xte.shape}")
    con.close()

    # train
    dev = "cpu"
    model = WinMLP(in_dim).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    crit = nn.BCEWithLogitsLoss()

    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=256, shuffle=True)

    best_val = -1
    os.makedirs(DEFAULT_DIR, exist_ok=True)
    t0 = time.time()
    for epoch in range(30):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            logit = model(xb)
            loss = crit(logit, yb)
            loss.backward()
            opt.step()
        # val
        model.eval()
        with torch.no_grad():
            lv = torch.from_numpy(Xv)
            pv = torch.sigmoid(model(lv)).numpy()
            acc = float(((pv > 0.5).astype(float) == yv).mean())
            brier = float(np.mean((pv - yv) ** 2))
        print(f"epoch {epoch:02d}  val_acc={acc:.3f}  brier={brier:.4f}")
        if acc > best_val:
            best_val = acc
            # calibration on val
            logits_v = model(torch.from_numpy(Xv)).detach().numpy()
            T = fit_temperature(logits_v, yv)
            torch.save({"model": model.state_dict(),
                        "in_dim": in_dim,
                        "temperature": T,
                        "val_acc": acc,
                        "brier": brier},
                       os.path.join(DEFAULT_DIR, "best.pt"))
            print(f"  saved (T={T:.2f})")
    print(f"training done in {time.time()-t0:.1f}s")

    # final test metrics
    ckpt = torch.load(os.path.join(DEFAULT_DIR, "best.pt"), weights_only=False)
    model.load_state_dict(ckpt["model"])
    T = ckpt["temperature"]
    model.eval()
    with torch.no_grad():
        logits_te = model(torch.from_numpy(Xte)).numpy() / T
        p_te = 1 / (1 + np.exp(-logits_te))
    acc = float(((p_te > 0.5).astype(float) == yte).mean())
    brier = float(np.mean((p_te - yte) ** 2))
    # ROC-AUC
    try:
        from sklearn.metrics import roc_auc_score
        auc = float(roc_auc_score(yte, p_te))
    except Exception:
        auc = float("nan")
    print(f"\n=== TEST ===")
    print(f"acc={acc:.3f}  auc={auc:.3f}  brier={brier:.4f}  T={T:.2f}")
    print(f"checkpoint: {os.path.join(DEFAULT_DIR, 'best.pt')}")


if __name__ == "__main__":
    main()
