"""Cyclone-centre localisation from IR (heatmap regression with soft-argmax).

Labels (weak): HURSAT images are centred on the interpolated best-track
centre, so after a known random shift the true centre position in the crop is
known exactly *relative to the best track*. Error therefore measures agreement
with best-track centres (which have their own ~20-50 km uncertainty).

Model: small fully-convolutional net -> 16x16 heatmap -> softmax -> expected
(x, y) (DSNT-style; Nibali et al. 2018). Loss: Euclidean distance (px).
Baselines: (a) no-information prior (predict crop centre), (b) coldest cloud
(argmin of 3x3-smoothed BT). Split: train on season blocks 0-3, test block 4.
"""
from __future__ import annotations

import copy
import json
import logging

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from tropicast import config
from tropicast.satellite.dataset import build_satset, normalise
from tropicast.satellite.features import PX_KM

log = logging.getLogger(__name__)
CROP, MAXSHIFT = 56, 10  # px; 10 px ~ 155 km


class CentreNet(nn.Module):
    def __init__(self):
        super().__init__()
        c = [1, 16, 32, 48, 64]
        layers = []
        for a, b in zip(c[:-1], c[1:]):
            layers += [nn.Conv2d(a, b, 3, padding=1), nn.BatchNorm2d(b), nn.ReLU()]
            if b in (16, 32):
                layers.append(nn.MaxPool2d(2))
        self.body = nn.Sequential(*layers)
        self.out = nn.Conv2d(64, 1, 1)

    def forward(self, x):
        h = self.out(self.body(x))[:, 0]                       # (n, 14, 14)
        n, H, W = h.shape
        p = F.softmax(h.reshape(n, -1), 1).reshape(n, H, W)
        ys = (torch.arange(H, dtype=torch.float32) + 0.5) / H * x.shape[-2]
        xs = (torch.arange(W, dtype=torch.float32) + 0.5) / W * x.shape[-1]
        return torch.stack([(p.sum(1) * xs).sum(1), (p.sum(2) * ys).sum(1)], 1), p


def _crops(imgs: np.ndarray, rng: np.random.Generator):
    n = len(imgs)
    c = (imgs.shape[-1] - CROP) // 2
    sh = rng.integers(-MAXSHIFT, MAXSHIFT + 1, size=(n, 2))
    out = np.stack([im[c + dy:c + dy + CROP, c + dx:c + dx + CROP] for im, (dx, dy) in zip(imgs, sh)])
    centre = np.stack([(CROP - 1) / 2 - sh[:, 0], (CROP - 1) / 2 - sh[:, 1]], 1) + 0.5  # true centre (x, y) px
    return out, centre.astype(np.float32)


def _coldest(crops: np.ndarray) -> np.ndarray:
    k = np.ones((3, 3)) / 9
    out = []
    for im in crops:
        x = F.pad(torch.from_numpy(im[None, None]).float(), (1, 1, 1, 1), mode="replicate")  # zero-pad would bias to edges
        sm = F.conv2d(x, torch.from_numpy(k[None, None]).float())[0, 0]
        y, x = np.unravel_index(int(sm.argmin()), sm.shape)
        out.append([x + 0.5, y + 0.5])
    return np.asarray(out, np.float32)


def run(epochs: int = 20, seed: int = 0) -> dict:
    s = build_satset()
    f = s.frame
    tr, te = s.subset((f["fold"] < 4).values), s.subset((f["fold"] == 4).values)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    te_x, te_c = _crops(te.images, np.random.default_rng(123))
    net = CentreNet()
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    va_x, va_c = _crops(tr.images[-400:], np.random.default_rng(7))
    trn = tr.images[:-400]
    best, best_state = np.inf, None
    for ep in range(epochs):
        net.train()
        x, c = _crops(trn, rng)
        X, C = torch.from_numpy(normalise(x))[:, None], torch.from_numpy(c)
        for idx in np.array_split(rng.permutation(len(X)), max(1, len(X) // 64)):
            pred, _ = net(X[idx])
            loss = torch.linalg.norm(pred - C[idx], dim=1).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vp, _ = net(torch.from_numpy(normalise(va_x))[:, None])
            vl = float(torch.linalg.norm(vp - torch.from_numpy(va_c), dim=1).mean())
        if vl < best:
            best, best_state = vl, copy.deepcopy(net.state_dict())
        log.info("centre epoch %d val err %.2f px", ep, vl)
    net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        p, _ = net(torch.from_numpy(normalise(te_x))[:, None])
    p = p.numpy()

    def stats(pred, m=None):
        m = np.ones(len(te_c), bool) if m is None else m
        e = np.linalg.norm(pred[m] - te_c[m], axis=1) * PX_KM
        return {"mean_km": round(float(e.mean()), 1), "median_km": round(float(np.median(e)), 1),
                "p90_km": round(float(np.percentile(e, 90)), 1)}

    wind = te.frame["wind"].values
    res = {
        "test_images": int(len(te_c)), "test_seasons": [int(te.frame["season"].min()), int(te.frame["season"].max())],
        "max_shift_km": round(MAXSHIFT * PX_KM, 1),
        "cnn_heatmap": stats(p),
        "baseline_crop_centre": stats(np.full_like(te_c, (CROP) / 2)),
        "baseline_coldest_cloud": stats(_coldest(te_x)),
        "cnn_by_intensity": {k: stats(p, m) | {"n": int(m.sum())} for k, m in
                             (("<34 kt", wind < 34), ("34-63 kt", (wind >= 34) & (wind < 64)), (">=64 kt", wind >= 64))
                             if m.any()},
        "label_note": "Reference = HURSAT/IBTrACS interpolated best-track centre (weak label).",
    }
    torch.save(net.state_dict(), config.artifacts_dir() / "centre_net.pt")
    (config.reports_dir() / "localization.json").write_text(json.dumps(res, indent=2))
    return res
