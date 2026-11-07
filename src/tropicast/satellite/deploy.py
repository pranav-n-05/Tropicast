"""Train the deployable satellite intensity CNN on all labelled imagery (after the CV study)."""
from __future__ import annotations

import json

import numpy as np
import torch

from tropicast import config
from tropicast.satellite.cnn import CNNEstimator
from tropicast.satellite.dataset import build_satset


def train_deploy(members: int = 3, epochs: int = 15) -> dict:
    s = build_satset()
    y = s.frame["wind"].values
    cnn = CNNEstimator(members=members, epochs=epochs, seed=999).fit(s.images, y)
    path = config.artifacts_dir() / "satellite_cnn.pt"
    rep = json.loads((config.reports_dir() / "satellite_evaluation.json").read_text()) \
        if (config.reports_dir() / "satellite_evaluation.json").exists() else {}
    q = float(np.mean([c["q"] for c in rep.get("cnn", {}).get("interval90", [])])) if rep else 1.645
    torch.save({"state": cnn.state(), "interval90_q": q,
                "trained_on": {"images": int(len(y)), "seasons": [int(s.frame["season"].min()),
                                                                   int(s.frame["season"].max())]}}, path)
    return {"path": str(path), "interval90_q": q, "images": int(len(y))}
