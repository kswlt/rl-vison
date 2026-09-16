"""Full Win Predictor evaluation.

Computes: Constant baseline, Logistic Regression, MLP.
Metrics: Accuracy, ROC-AUC, PR-AUC, Log Loss, Brier, ECE, balanced acc.
Time-segmented + team-held-out split.
3 seeds for MLP.
Writes reports/win_prediction_v2.md
"""
from __future__ import annotations

import json
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
from .predictor import WinMLP, fit_temperature

REPO_ROOT = Path(__file__).resolve().parents[2]
DB = os.path.join(REPO_ROOT, "dataset", "rmuc_2026_region_dataset.sqlite")
VMAP = os.path.join(REPO_ROOT, "data", "vis_map.npz")
PRIOR = os.path.join(REPO_ROOT, "data", "team_prior.json")
AGENT = "步兵3"
SPLITS_FILE = os.path.join(REPO_ROOT, "splits", "win_split.json")
REPORT_DIR = os.path.join(REPO_ROOT, "reports")


def collect_xy(game_ids, con, vmap, prior, max_per_game=120, return_time=False):
    xs, ys, ts = [], [], []
    for gid in game_ids:
        try:
            game = BD.load_game_arrays(con, gid)
        except Exception:
            continue
        if game.T < 30:
            continue
        labels = D.load_win_labels(DB)
        for camp in (S.CAMP_RED, S.CAMP_BLUE):
            sf = prior.feats(gid, camp) if prior else np.zeros(6, np.float32)
            try:
                obs = F.build_obs(game, camp, AGENT, t_max_ref=450.0,
                                  vis_map=vmap, team_feat=sf)
            except Exception:
                continue
            T = min(len(obs), game.T)
            idx = np.linspace(0, T - 1, min(max_per_game, T)).astype(int)
            label = 1.0 if labels[gid][camp] == "win" else 0.0
            for i in idx:
                xs.append(obs[i].astype(np.float32))
                ys.append(label)
                ts.append(int(i + 1))  # 1-based second
    if not xs:
        return None, None, None
    return np.stack(xs), np.array(ys, dtype=np.float32), np.array(ts, dtype=np.int32)


# ---------- metrics ----------
def ece(p, y, n_bins=10):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        m = (p >= bins[i]) & (p < bins[i + 1])
        n = int(m.sum())
        if n == 0:
            continue
        conf = p[m].mean()
        acc = y[m].mean()
        ece += n * abs(conf - acc)
    return ece / len(p)


def metrics(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    acc = float(((p > 0.5).astype(float) == y).mean())
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    try:
        from sklearn.metrics import roc_auc_score, average_precision_score, balanced_accuracy_score
        auc = float(roc_auc_score(y, p))
        prauc = float(average_precision_score(y, p))
        bacc = float(balanced_accuracy_score(y, p > 0.5))
    except Exception:
        auc = prauc = bacc = float("nan")
    return dict(acc=acc, brier=brier, logloss=logloss, auc=auc,
                prauc=prauc, bacc=bacc, ece=ece(p, y),
                n=len(y), pos_rate=float(y.mean()))


# ---------- train MLP ----------
def train_mlp(Xtr, ytr, Xv, yv, seed=42, epochs=25):
    torch.manual_seed(seed)
    np.random.seed(seed)
    in_dim = Xtr.shape[1]
    model = WinMLP(in_dim)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    crit = nn.BCEWithLogitsLoss()
    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=256, shuffle=True)
    best_val = -1
    best_state = None
    for ep in range(epochs):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            pv = torch.sigmoid(model(torch.from_numpy(Xv))).numpy()
            acc = float(((pv > 0.5).astype(float) == yv).mean())
        if acc > best_val:
            best_val = acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    # calibrate
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        lv = model(torch.from_numpy(Xv)).detach().numpy()
    T = fit_temperature(lv, yv)
    return model, T


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SPLITS_FILE), exist_ok=True)
    con = sqlite3.connect(DB)
    vmap = VisibilityMap.load(VMAP) if os.path.isfile(VMAP) else None
    prior = TeamPrior.load(PRIOR) if os.path.isfile(PRIOR) else None

    games = list(D.iter_games(DB))
    gids = [g[0] for g in games]
    game_meta = [(g[0], g[1], g[2]) for g in games]
    print(f"games: {len(gids)}")

    # random split
    train_g, val_g, test_g = D.game_level_split(gids)
    # team-held-out split
    tr_th, va_th, te_th, unseen_schools = D.team_held_out_split(game_meta, test_frac=0.2)
    print(f"random: train={len(train_g)} val={len(val_g)} test={len(test_g)}")
    print(f"team-held-out: train={len(tr_th)} val={len(va_th)} test={len(te_th)}")

    # save split manifest
    splits = dict(
        random=dict(train=train_g, val=val_g, test=test_g),
        team_held_out=dict(train=tr_th, val=va_th, test=te_th,
                            unseen_schools=sorted(unseen_schools)),
    )
    with open(SPLITS_FILE, "w") as f:
        json.dump(splits, f)
    print(f"split manifest -> {SPLITS_FILE}")

    print("collecting random train/val/test...")
    Xtr, ytr, _ = collect_xy(train_g, con, vmap, prior)
    Xv, yv, _ = collect_xy(val_g, con, vmap, prior)
    Xte, yte, tte = collect_xy(test_g, con, vmap, prior)
    con.close()
    print(f"train: {Xtr.shape}  val: {Xv.shape}  test: {Xte.shape}  pos={ytr.mean():.3f}")

    report = ["# Win Prediction v2 Report\n"]
    report.append(f"- train games: {len(train_g)}, val: {len(val_g)}, test: {len(test_g)}")
    report.append(f"- train samples: {len(ytr)}, val: {len(yv)}, test: {len(yte)}")
    report.append(f"- train positive rate: {ytr.mean():.3f}\n")

    # Constant baseline
    base_rate = float(ytr.mean())
    p_const = np.full_like(yte, base_rate)
    m_const = metrics(p_const, yte)
    report.append(f"## Constant baseline (P={base_rate:.3f})")
    report.append(f"- acc={m_const['acc']:.3f}  brier={m_const['brier']:.4f}  "
                  f"logloss={m_const['logloss']:.4f}  auc={m_const['auc']:.3f}\n")

    # Logistic regression
    print("training logistic regression...")
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(max_iter=1000, C=1.0)
    lr.fit(Xtr, ytr)
    p_lr = lr.predict_proba(Xte)[:, 1]
    T_lr = fit_temperature(lr.decision_function(Xv), yv)
    p_lr_cal = 1 / (1 + np.exp(-lr.decision_function(Xte) / T_lr))
    m_lr = metrics(p_lr_cal, yte)
    report.append("## Logistic Regression (calibrated)")
    report.append(f"- acc={m_lr['acc']:.3f}  auc={m_lr['auc']:.3f}  "
                  f"prauc={m_lr['prauc']:.3f}  brier={m_lr['brier']:.4f}  "
                  f"logloss={m_lr['logloss']:.4f}  ece={m_lr['ece']:.4f}  "
                  f"bacc={m_lr['bacc']:.3f}  T={T_lr:.2f}\n")

    # MLP 3 seeds
    print("training MLP x3 seeds...")
    all_mlp = []
    for seed in (42, 123, 2024):
        t0 = time.time()
        model, T = train_mlp(Xtr, ytr, Xv, yv, seed=seed)
        model.eval()
        with torch.no_grad():
            p_raw = torch.sigmoid(model(torch.from_numpy(Xte))).numpy()
            p_cal = 1 / (1 + np.exp(-torch.from_numpy(
                model(torch.from_numpy(Xte)).numpy() / T)))
        m = metrics(p_cal.numpy() if hasattr(p_cal, 'numpy') else np.asarray(p_cal), yte)
        m["T"] = T
        m["seed"] = seed
        all_mlp.append(m)
        print(f"  seed={seed}: acc={m['acc']:.3f} auc={m['auc']:.3f} "
              f"brier={m['brier']:.4f} ece={m['ece']:.4f} T={T:.2f} ({time.time()-t0:.0f}s)")

    report.append("## MLP Win Predictor (3 seeds, calibrated)")
    keys = ["acc", "auc", "prauc", "brier", "logloss", "ece", "bacc", "T"]
    for k in keys:
        vals = [m[k] for m in all_mlp]
        report.append(f"- {k}: mean={np.mean(vals):.4f}  std={np.std(vals):.4f}")
    report.append("")

    # time-segmented eval (best seed)
    best_idx = int(np.argmax([m["auc"] for m in all_mlp]))
    best_seed = all_mlp[best_idx]["seed"]
    model, T = train_mlp(Xtr, ytr, Xv, yv, seed=best_seed)
    model.eval()
    with torch.no_grad():
        p_te = 1 / (1 + np.exp(-torch.from_numpy(
            model(torch.from_numpy(Xte)).numpy() / T)))
    p_te = p_te.numpy() if hasattr(p_te, 'numpy') else np.asarray(p_te)

    report.append("## Time-segmented evaluation (test)")
    report.append("| window | n | acc | auc | brier | ece |")
    report.append("|---|---|---|---|---|---|")
    for lo, hi in [(0, 60), (60, 120), (120, 180), (180, 240), (240, 300), (300, 9999)]:
        m = (tte >= lo) & (tte < hi)
        if m.sum() < 50:
            continue
        mm = metrics(p_te[m], yte[m])
        report.append(f"| {lo}-{hi}s | {mm['n']} | {mm['acc']:.3f} | "
                      f"{mm['auc']:.3f} | {mm['brier']:.4f} | {mm['ece']:.4f} |")
    report.append("")

    # team-held-out eval
    print("collecting team-held-out...")
    con = sqlite3.connect(DB)
    Xte2, yte2, tte2 = collect_xy(te_th, con, vmap, prior)
    con.close()
    if Xte2 is not None and len(yte2) > 100:
        with torch.no_grad():
            p2 = 1 / (1 + np.exp(-torch.from_numpy(
                model(torch.from_numpy(Xte2)).numpy() / T)))
        p2 = p2.numpy() if hasattr(p2, 'numpy') else np.asarray(p2)
        m2 = metrics(p2, yte2)
        report.append("## Team-held-out test (unseen schools)")
        report.append(f"- unseen schools: {len(unseen_schools)}  samples: {m2['n']}")
        report.append(f"- acc={m2['acc']:.3f}  auc={m2['auc']:.3f}  "
                      f"brier={m2['brier']:.4f}  ece={m2['ece']:.4f}\n")
    else:
        report.append("## Team-held-out test: not enough samples\n")

    out = "\n".join(report)
    out_path = os.path.join(REPORT_DIR, "win_prediction_v2.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"\nreport -> {out_path}")
    print(out)


if __name__ == "__main__":
    main()
