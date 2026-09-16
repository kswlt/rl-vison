"""WinQ: Q_win(s,a) = P(final win | s, a).

Supervised action-conditioned outcome model.
Input: concat(161-D state, tactical action vector) -> MLP -> sigmoid.
Action vector dimensions are read from the existing action_spec — never hardcoded.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = os.path.join(REPO_ROOT, "rm_runs", "winq_supervised")


class WinQNet(nn.Module):
    def __init__(self, state_dim: int, act_dim: int,
                 hidden=(256, 256, 128), dropout=0.2):
        super().__init__()
        layers = []
        prev = state_dim + act_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.LayerNorm(h), nn.GELU(), nn.Dropout(dropout)]
            prev = h
        layers += [nn.Linear(prev, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, s: torch.Tensor, a: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([s, a], dim=-1)).squeeze(-1)


class WinQ:
    def __init__(self, state_dim: int, act_dim: int,
                 ckpt_dir: str = DEFAULT_DIR, device="cpu"):
        self.state_dim = state_dim
        self.act_dim = act_dim
        self.ckpt_dir = ckpt_dir
        self.device = device
        self.model = WinQNet(state_dim, act_dim).to(device)
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
    def predict(self, s: np.ndarray, a: np.ndarray, calibrated=True) -> float:
        if not self.loaded:
            raise RuntimeError("WinQ not loaded")
        s_t = torch.as_tensor(s, dtype=torch.float32, device=self.device).unsqueeze(0)
        a_t = torch.as_tensor(a, dtype=torch.float32, device=self.device).unsqueeze(0)
        logit = float(self.model(s_t, a_t).item())
        if calibrated:
            logit /= self.temperature
        return float(np.clip(1 / (1 + np.exp(-logit)), 0.0, 1.0))

    @torch.no_grad()
    def predict_batch(self, s: np.ndarray, a: np.ndarray, calibrated=True) -> np.ndarray:
        if not self.loaded:
            raise RuntimeError("WinQ not loaded")
        s_t = torch.as_tensor(s, dtype=torch.float32, device=self.device)
        a_t = torch.as_tensor(a, dtype=torch.float32, device=self.device)
        logits = self.model(s_t, a_t).cpu().numpy()
        if calibrated:
            logits = logits / self.temperature
        return np.clip(1 / (1 + np.exp(-logits)), 0.0, 1.0)
