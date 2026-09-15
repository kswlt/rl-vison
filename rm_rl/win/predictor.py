"""Win Predictor: P(win | s) as a calibrated binary classifier.

Architecture: 161 -> 256 -> 256 -> 128 -> 1 sigmoid (LayerNorm + dropout).
Trained with BCE loss, episode-balanced sampling so long games don't dominate.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = os.path.join(REPO_ROOT, "rm_runs", "win_predictor")


class WinMLP(nn.Module):
    def __init__(self, in_dim: int, hidden=(256, 256, 128), dropout=0.2):
        super().__init__()
        layers = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.LayerNorm(h), nn.GELU(), nn.Dropout(dropout)]
            prev = h
        layers += [nn.Linear(prev, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)  # logits


def fit_temperature(logits_val: np.ndarray, labels_val: np.ndarray) -> float:
    """Find T that minimises BCE on the validation set (1-D search)."""
    best_T, best_ll = 1.0, -1e9
    for T in np.linspace(0.5, 5.0, 91):
        p = 1.0 / (1.0 + np.exp(-logits_val / T))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        ll = float(np.mean(labels_val * np.log(p) + (1 - labels_val) * np.log(1 - p)))
        if ll > best_ll:
            best_ll, best_T = ll, float(T)
    return best_T


class WinPredictor:
    """Thin wrapper around WinMLP for inference + calibration."""

    def __init__(self, in_dim: int, ckpt_dir: str = DEFAULT_DIR, device="cpu"):
        self.in_dim = in_dim
        self.ckpt_dir = ckpt_dir
        self.device = device
        self.model = WinMLP(in_dim).to(device)
        self.temperature = 1.0
        self.loaded = False

    def load(self) -> bool:
        p = os.path.join(self.ckpt_dir, "best.pt")
        if not os.path.isfile(p):
            return False
        ckpt = torch.load(p, map_location=self.device, weights_only=False)
        self.model.load_state_dict(ckpt["model"])
        self.temperature = float(ckpt.get("temperature", 1.0))
        self.model.eval()
        self.loaded = True
        return True

    @torch.no_grad()
    def predict(self, obs: np.ndarray, calibrated=True) -> float:
        if not self.loaded:
            raise RuntimeError("WinPredictor not loaded")
        x = torch.as_tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
        logit = float(self.model(x).item())
        if calibrated:
            logit /= self.temperature
        p = 1.0 / (1.0 + np.exp(-logit))
        return float(np.clip(p, 0.0, 1.0))

    @torch.no_grad()
    def predict_batch(self, obs: np.ndarray, calibrated=True) -> np.ndarray:
        if not self.loaded:
            raise RuntimeError("WinPredictor not loaded")
        x = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        logits = self.model(x).cpu().numpy()
        if calibrated:
            logits = logits / self.temperature
        p = 1.0 / (1.0 + np.exp(-logits))
        return np.clip(p, 0.0, 1.0)
