"""Satellite product for one storm image: CNN intensity estimate + uncertainty + Grad-CAM.

HURSAT archive ends in 2015, so this product exists only for historical storms
(research / hindcast). Labelled RESEARCH_SATELLITE_ESTIMATE in every payload.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
import torch

from tropicast import config
from tropicast.satellite.cnn import CROP, CNNEstimator
from tropicast.satellite.dataset import _fill, npz_dir
from tropicast.satellite.features import IR_FEATURES, ir_features


@lru_cache(maxsize=1)
def model() -> tuple[CNNEstimator, float, dict]:
    p = config.artifacts_dir() / "satellite_cnn.pt"
    if not p.exists():
        raise FileNotFoundError("Satellite CNN not trained. Run `tropicast satellite`.")
    blob = torch.load(p, weights_only=False)
    return CNNEstimator.from_state(blob["state"]), float(blob["interval90_q"]), blob["trained_on"]


def available(sid: str) -> list[str]:
    f = npz_dir() / f"{sid}.npz"
    if not f.exists():
        return []
    return [pd.Timestamp(int(t), tz="UTC").isoformat() for t in np.load(f)["time"]]


def product(sid: str, time: str | None = None, label_wind: float | None = None,
            label_agency: str | None = None) -> dict:
    f = npz_dir() / f"{sid}.npz"
    if not f.exists():
        raise LookupError("No HURSAT imagery for this storm (archive covers 1978-2015, VZA <= 65 deg).")
    z = np.load(f)
    times = np.array([pd.Timestamp(int(t), tz="UTC") for t in z["time"]])
    if time is None:
        i = len(times) - 1
    else:
        t = pd.Timestamp(time)
        t = t.tz_localize("UTC") if t.tzinfo is None else t
        i = int(np.argmin(np.abs(z["time"].astype(np.int64) - t.value)))  # nearest image (int64 ns)
    img = _fill(z["ir"][i])
    prev = np.full_like(img, np.nan)
    j = np.flatnonzero(times == times[i] - pd.Timedelta(hours=6))
    if len(j):
        prev = _fill(z["ir"][j[0]])
    cnn, q, trained = model()
    p = cnn.predict(img[None])
    cam = cnn.gradcam(img)
    feats = dict(zip(IR_FEATURES, ir_features(img[None], prev[None])[0].tolist()))
    meta = json.loads(str(z["meta"]))[i] if "meta" in z.files else {}
    off = (img.shape[0] - CROP) // 2
    return {
        "product": "RESEARCH_SATELLITE_ESTIMATE",
        "disclaimer": config.DISCLAIMER,
        "sid": sid, "time": times[i].isoformat(), "satellite": str(z["sat"][i]), "vza_deg": round(float(z["vza"][i]), 1),
        "available_times": [t.isoformat() for t in times],
        "image_bt_k": np.round(img).astype(int).tolist(), "pixel_km": 15.5,
        "gradcam": np.round(cam, 3).tolist(), "gradcam_offset_px": off,
        "cnn_wind_kt": round(float(p["mean"][0]), 1),
        "cnn_wind_kt_90": [round(float(p["mean"][0] - q * p["sd"][0]), 1), round(float(p["mean"][0] + q * p["sd"][0]), 1)],
        "best_track_wind_kt": label_wind, "best_track_agency": label_agency,
        "ir_features": {k: (None if not np.isfinite(v) else round(v, 3)) for k, v in feats.items()},
        "archer": {k: (None if not np.isfinite(v) else round(v, 2)) for k, v in meta.items()},
        "model": {"name": "satellite_cnn", "trained_on": trained,
                  "interval": "90 % normalised-conformal (factor from nested CV)",
                  "note": "Trained on all 1982-2015 images; numbers for historical images include training data. "
                          "Unbiased skill: reports/satellite_evaluation.md (nested CV)."},
        "explainability_note": "Grad-CAM highlights pixels that most increase the predicted intensity. It is an "
                               "interpretive aid, not proof of physical causation.",
    }
