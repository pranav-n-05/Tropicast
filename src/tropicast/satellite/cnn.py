"""CNN intensity estimator on HURSAT IR (satellite-only modality) + Grad-CAM.

Architecture: 4 conv blocks (BN, ReLU, max-pool) -> global average pool ->
dense -> (mean, log-variance) of wind (Gaussian NLL, heteroscedastic).
Augmentation: random rotation (any angle) and small translation. NO mirror
flips: mirroring reverses the cyclonic spiral (counter-clockwise in the NH)
and would create physically impossible storms.
Inference: average over 8 rotations (test-time augmentation).
"""
from __future__ import annotations

import copy
import logging
import math

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from tropicast.satellite.dataset import normalise

log = logging.getLogger(__name__)
CROP = 64


def _rotate(x: torch.Tensor, angles: torch.Tensor, shift: torch.Tensor | None = None) -> torch.Tensor:
    cos, sin = torch.cos(angles), torch.sin(angles)
    theta = torch.zeros(len(x), 2, 3)
    theta[:, 0, 0], theta[:, 0, 1], theta[:, 1, 0], theta[:, 1, 1] = cos, -sin, sin, cos
    if shift is not None:
        theta[:, :, 2] = shift
    grid = F.affine_grid(theta, list(x.shape), align_corners=False)
    return F.grid_sample(x, grid, padding_mode="border", align_corners=False)


def _center_crop(x: torch.Tensor, size: int = CROP) -> torch.Tensor:
    o = (x.shape[-1] - size) // 2
    return x[..., o:o + size, o:o + size]


class IntensityCNN(nn.Module):
    def __init__(self, ch=(16, 32, 48, 64), dropout=0.2):
        super().__init__()
        layers, cin = [], 1
        for c in ch:
            layers += [nn.Conv2d(cin, c, 3, padding=1), nn.BatchNorm2d(c), nn.ReLU(),
                       nn.Conv2d(c, c, 3, padding=1), nn.BatchNorm2d(c), nn.ReLU(), nn.MaxPool2d(2)]
            cin = c
        self.features = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(dropout), nn.Linear(cin, 64), nn.ReLU(),
                                  nn.Linear(64, 2))

    def embed(self, x):
        return F.adaptive_avg_pool2d(self.features(x), 1)

    def forward(self, x):
        o = self.head(self.embed(x))
        return o[:, 0], o[:, 1].clamp(-6, 6)


class CNNEstimator:
    """Trains an ensemble of IntensityCNN models; predicts mean, sd, embedding."""

    def __init__(self, members=2, epochs=25, lr=2e-3, batch_size=64, patience=6, seed=0):
        self.k, self.epochs, self.lr, self.bs, self.patience, self.seed = members, epochs, lr, batch_size, patience, seed
        self.nets: list[IntensityCNN] = []
        self.y_mu, self.y_sd = 0.0, 1.0

    def _x(self, bt: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(normalise(bt).astype(np.float32))[:, None]

    def fit(self, bt: np.ndarray, y: np.ndarray, bt_val: np.ndarray | None = None, y_val: np.ndarray | None = None):
        torch.set_num_threads(max(1, torch.get_num_threads()))
        X, Y = self._x(bt), torch.from_numpy(y.astype(np.float32))
        self.y_mu, self.y_sd = float(y.mean()), float(y.std() + 1e-6)
        Yn = (Y - self.y_mu) / self.y_sd
        Xv = self._x(bt_val) if bt_val is not None else None
        Yv = ((torch.from_numpy(y_val.astype(np.float32)) - self.y_mu) / self.y_sd) if y_val is not None else None
        self.nets = []
        for m in range(self.k):
            torch.manual_seed(self.seed + m)
            rng = np.random.default_rng(self.seed + m)
            net = IntensityCNN()
            opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=1e-4)
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, self.epochs)
            best, best_state, bad = math.inf, None, 0
            for ep in range(self.epochs):
                net.train()
                for idx in np.array_split(rng.permutation(len(X)), max(1, len(X) // self.bs)):
                    xb = X[idx]
                    ang = torch.from_numpy(rng.uniform(0, 2 * np.pi, len(idx)).astype(np.float32))
                    sh = torch.from_numpy(rng.uniform(-0.06, 0.06, (len(idx), 2)).astype(np.float32))
                    xb = _center_crop(_rotate(xb, ang, sh))
                    mu, lv = net(xb)
                    loss = (0.5 * (lv + (Yn[idx] - mu) ** 2 / lv.exp())).mean()
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
                sched.step()
                if Xv is None:
                    best_state = copy.deepcopy(net.state_dict())
                    continue
                net.eval()
                with torch.no_grad():
                    mu, lv = net(_center_crop(Xv))
                    vl = float((0.5 * (lv + (Yv - mu) ** 2 / lv.exp())).mean())
                if vl < best - 1e-4:
                    best, best_state, bad = vl, copy.deepcopy(net.state_dict()), 0
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
            net.load_state_dict(best_state)
            net.eval()
            self.nets.append(net)
            log.info("CNN member %d done (epoch %d, val nll %.3f)", m, ep, best)
        return self

    @torch.no_grad()
    def predict(self, bt: np.ndarray, tta: int = 8, batch: int = 256) -> dict[str, np.ndarray]:
        X = self._x(bt)
        mus, vars_, embs = [], [], []
        for net in self.nets:
            m_all, v_all, e_all = [], [], []
            for i in range(0, len(X), batch):
                xb = X[i:i + batch]
                ms, vs, es = [], [], []
                for k in range(tta):
                    ang = torch.full((len(xb),), 2 * np.pi * k / tta)
                    xr = _center_crop(_rotate(xb, ang))
                    mu, lv = net(xr)
                    ms.append(mu)
                    vs.append(lv.exp())
                    es.append(net.embed(xr).flatten(1))
                m_all.append(torch.stack(ms).mean(0))
                v_all.append(torch.stack(vs).mean(0) + torch.stack(ms).var(0))
                e_all.append(torch.stack(es).mean(0))
            mus.append(torch.cat(m_all))
            vars_.append(torch.cat(v_all))
            embs.append(torch.cat(e_all))
        mu = torch.stack(mus)
        var = torch.stack(vars_).mean(0) + mu.var(0) if len(self.nets) > 1 else torch.stack(vars_).mean(0)
        return {"mean": (mu.mean(0) * self.y_sd + self.y_mu).numpy(),
                "sd": (var.sqrt() * self.y_sd).numpy(),
                "embedding": torch.stack(embs).mean(0).numpy()}

    def gradcam(self, bt: np.ndarray) -> np.ndarray:
        """Grad-CAM (Selvaraju et al., 2017) of the predicted mean w.r.t. the last conv block.

        Returns a (CROP, CROP) heatmap in [0, 1] averaged over ensemble members.
        Interpretive aid only - not evidence of physical causation.
        """
        x = _center_crop(self._x(bt[None]))
        maps = []
        for net in self.nets:
            acts = {}
            last = [m for m in net.features if isinstance(m, nn.ReLU)][-1]
            h1 = last.register_forward_hook(lambda m, i, o: acts.__setitem__("a", o))
            xx = x.clone().requires_grad_(False)
            net.zero_grad()
            mu, _ = net(xx)
            a = acts["a"]
            g = torch.autograd.grad(mu.sum(), a)[0]
            w = g.mean(dim=(2, 3), keepdim=True)
            cam = F.relu((w * a).sum(1, keepdim=True))
            cam = F.interpolate(cam, size=x.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
            maps.append(cam.detach().numpy())
            h1.remove()
        cam = np.mean(maps, 0)
        return cam / (cam.max() + 1e-9)

    def state(self) -> dict:
        return {"k": self.k, "y_mu": self.y_mu, "y_sd": self.y_sd, "nets": [n.state_dict() for n in self.nets]}

    @classmethod
    def from_state(cls, st: dict) -> "CNNEstimator":
        obj = cls(members=st["k"])
        obj.y_mu, obj.y_sd = st["y_mu"], st["y_sd"]
        for sd in st["nets"]:
            n = IntensityCNN()
            n.load_state_dict(sd)
            n.eval()
            obj.nets.append(n)
        return obj
