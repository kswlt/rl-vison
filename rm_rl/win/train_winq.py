"""Train supervised WinQ: Q_win(s,a) = P(win | s, a).

Reuses the exact same game_id split as the Win Predictor (splits/win_split.json).
Action vector: tactical (gx, gy, fire_gate, target[7]) = 10-D.
"""
from __future__ import annotations

import json
import os
import sqlite3
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
from .predictor import fit_temperature
from .winq import WinQNet, DEFAULT_DIR

REPO_ROOT = Path(__file__).resolve().parents[2]
DB = os.path.join(REPO_ROOT, "dataset", "rmuc_2026_region_dataset.sqlite")
VMAP = os.path.join(REPO_ROOT, "data", "vis_map.npz")
PRIOR = os.path.join(REPO_ROOT, "data", "team_prior.json")
AGENT = "步兵3"
SPLITS_FILE = os.path.join(REPO_ROOT, "splits", "win_split.json")


def collect_xy_a(game_ids, con, vmap, prior, max_per_game=120):
    xs, ys, a_s = [], [], []
    labels = D_labels = None
    import sqlite3 as sq
    con2 = sq.connect(DB)
    labs = {}
    for gid, winner in con2.execute('SELECT game_id, "胜方" FROM matches').fetchall():
        labs[int(gid)] = winner
    con2.close()
    for gid in game_ids:
        try:
            game = BD.load_game_arrays(con, gid)
        except Exception:
            continue
        if game.T < 30:
            continue
        winner = labs.get(gid)
        if not winner:
            continue
        for camp in (S.CAMP_RED, S.CAMP_BLUE):
            sf = prior.feats(gid, camp) if prior else np.zeros(6, np.float32)
            try:
                obs = F.build_obs(game, camp, AGENT, t_max_ref=450.0,
                                  vis_map=vmap, team_feat=sf)
                act = F.build_action_raw(game, camp, AGENT,
                                         action_mode="tactical", goal_horizon=5)
            except Exception:
                continue
            T = min(len(obs), len(act), game.T)
            idx = np.linspace(0, T - 1, min(max_per_game, T)).astype(int)
            label = 1.0 if winner == camp else 0.0
            for i in idx:
                xs.append(obs[i].astype(np.float32))
                ys.append(label)
                a_s.append(act[i].astype(np.float32))
    if not xs:
        return None, None, None
    return np.stack(xs), np.array(ys, dtype=np.float32), np.stack(a_s)


def main():
    print("=== WinQ supervised training ===")
    with open(SPLITS_FILE) as f:
        splits = json.load(f)
    train_g = splits["random"]["train"]
    val_g = splits["random"]["val"]
    test_g = splits["random"]["test"]
    print(f"train games={len(train_g)} val={len(val_g)} test={len(test_g)}")

    con = sqlite3.connect(DB)
    vmap = VisibilityMap.load(VMAP) if os.path.isfile(VMAP) else None
    prior = TeamPrior.load(PRIOR) if os.path.isfile(PRIOR) else None

    print("collecting train...")
    Xtr, ytr, Atr = collect_xy_a(train_g, con, vmap, prior)
    print(f"  Xtr={Xtr.shape}  Atr={Atr.shape}")
    print("collecting val...")
    Xv, yv, Av = collect_xy_a(val_g, con, vmap, prior)
    print("collecting test...")
    Xte, yte, Ate = collect_xy_a(test_g, con, vmap, prior)
    con.close()
    print(f"  Xte={Xte.shape}  pos_rate={ytr.mean():.3f}")

    state_dim = Xtr.shape[1]
    act_dim = Atr.shape[1]
    print(f"state_dim={state_dim}  act_dim={act_dim}")

    model = WinQNet(state_dim, act_dim)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    crit = nn.BCEWithLogitsLoss()
    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(Atr),
                       torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=256, shuffle=True)

    best_val = -1
    os.makedirs(DEFAULT_DIR, exist_ok=True)
    for ep in range(20):
        model.train()
        for s, a, y in dl:
            opt.zero_grad()
            loss = crit(model(s, a), y)
            loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            pv = torch.sigmoid(model(torch.from_numpy(Xv),
                                     torch.from_numpy(Av))).numpy()
            acc = float(((pv > 0.5).astype(float) == yv).mean())
        print(f"epoch {ep:02d}  val_acc={acc:.3f}")
        if acc > best_val:
            best_val = acc
            lv = model(torch.from_numpy(Xv), torch.from_numpy(Av)).detach().numpy()
            T = fit_temperature(lv, yv)
            torch.save({"model": model.state_dict(),
                        "state_dim": state_dim, "act_dim": act_dim,
                        "temperature": T, "val_acc": acc},
                       os.path.join(DEFAULT_DIR, "best.pt"))
            print(f"  saved T={T:.2f}")

    # test metrics
    ckpt = torch.load(os.path.join(DEFAULT_DIR, "best.pt"), weights_only=False)
    model.load_state_dict(ckpt["model"])
    T = ckpt["temperature"]
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(Xte), torch.from_numpy(Ate)).numpy() / T
        p = 1 / (1 + np.exp(-logits))
    from sklearn.metrics import roc_auc_score
    acc = float(((p > 0.5).astype(float) == yte).mean())
    auc = float(roc_auc_score(yte, p))
    brier = float(np.mean((p - yte) ** 2))
    print(f"\n=== WinQ TEST === acc={acc:.3f}  auc={auc:.3f}  brier={brier:.4f}  T={T:.2f}")


if __name__ == "__main__":
    main()
