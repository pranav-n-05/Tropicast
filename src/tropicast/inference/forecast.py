"""Inference: load registered models and issue a forecast for one storm at one time.

Every forecast carries: point estimates, calibrated uncertainty (67 % / 90 %
track radii, 90 % wind interval, category probabilities), input-data status,
model/data version identifiers and the operational disclaimer.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import torch

from tropicast import config
from tropicast.classification import imd
from tropicast.datasets.samples import build_samples
from tropicast.geospatial.geo import destination, km_to_displacement
from tropicast.models.baselines import PersistenceResidual
from tropicast.models.gru import GRUEnsemble
from tropicast.models.uncertainty import ConformalCalibrator


class ModelsNotTrainedError(RuntimeError):
    pass


@dataclass
class Loaded:
    meta: dict
    model: Any
    cal: ConformalCalibrator


def _load_one(meta: dict) -> Loaded:
    path = config.PROJECT_ROOT / meta["path"]
    try:
        blob = torch.load(path, weights_only=False)
    except Exception:  # sklearn pickle
        with path.open("rb") as fh:
            blob = pickle.load(fh)
    if blob["kind"] == "gru":
        m = GRUEnsemble.from_state(blob["state"])
        if blob.get("residual"):
            m = PersistenceResidual(m)
    else:
        m = blob["model"]
    return Loaded(meta, m, ConformalCalibrator.from_state(blob["cal"]))


@lru_cache(maxsize=1)
def load_registry() -> dict:
    p = config.artifacts_dir() / "registry.json"
    if not p.exists():
        raise ModelsNotTrainedError("No trained models. Run `tropicast train`.")
    reg = json.loads(p.read_text())
    reg["_track"] = _load_one(reg["track_model"])
    reg["_wind"] = _load_one(reg["intensity_model"])
    reg["_ref"] = _load_one(reg["reference_model"])
    with (config.PROJECT_ROOT / reg["ri_model"]["path"]).open("rb") as fh:
        reg["_ri"] = pickle.load(fh)
    ev = config.reports_dir() / "evaluation.json"
    reg["_ri_skill"] = None
    if ev.exists():
        rep = json.loads(ev.read_text())
        kind = rep["selection"]["ri"].removeprefix("ri_")
        reg["_ri_skill"] = {s: rep["rapid_intensification"][s][kind]["brier_skill"] for s in ("val", "test")}
    return reg


def reset_cache() -> None:
    load_registry.cache_clear()


def _cone(lat: float, lon: float, radius_km: float, n: int = 36) -> list[list[float]]:
    br = np.linspace(0, 360, n, endpoint=False)
    la, lo = destination(np.full(n, lat), np.full(n, lon), br, np.full(n, radius_km))
    return [[round(float(a), 3), round(float(b), 3)] for a, b in zip(la, lo)]


def forecast_storm(track: pd.DataFrame, issue_time: pd.Timestamp | None = None,
                   env: pd.DataFrame | None = None) -> dict:
    """Forecast from a single storm's tidy track (all agencies allowed, but flagged).

    Args:
        track: tidy rows for one ``sid`` (see :mod:`tropicast.preprocessing.tracks`).
        issue_time: forecast base time; default = latest observation with wind.
    """
    reg = load_registry()
    cfg = config.load("training")
    t = track[track["wind_kt"].notna()].sort_values("time")
    if t.empty:
        raise ValueError("Storm has no intensity observations; cannot forecast.")
    if issue_time is None:
        issue_time = t["time"].iloc[-1]
    issue_time = pd.Timestamp(issue_time)
    if issue_time.tzinfo is None:
        issue_time = issue_time.tz_localize("UTC")
    hist = t[t["time"] <= issue_time]
    agency = hist["agency"].iloc[-1] if len(hist) else None
    cfg_inf = {**cfg, "min_wind_kt": 0}
    s = build_samples(hist[hist["agency"] == agency], agency=None, cfg=cfg_inf, env=env)
    if len(s.frame) == 0:
        raise ValueError("Not enough history (need >= 2 positions 6 h apart ending at issue time).")
    s = s.subset((s.frame["t0"] == issue_time).values)
    if len(s.frame) == 0:
        raise ValueError(f"No observation at issue time {issue_time} with 6-h history.")

    tl, wl = reg["_track"], reg["_wind"]
    pt, pw = tl.model.predict(s), wl.model.predict(s)
    r67, r90 = tl.cal.track_radius(pt, 0.67)[0], tl.cal.track_radius(pt, 0.9)[0]
    wlo, whi = wl.cal.wind_interval(pw, 0.9)
    lat0, lon0 = float(s.frame["lat"].iat[0]), float(s.frame["lon"].iat[0])
    w0 = float(s.frame["wind"].iat[0])
    flat, flon = km_to_displacement(lat0, lon0, pt["dx"][0], pt["dy"][0])

    warnings: list[str] = []
    if agency != "newdelhi":
        warnings.append(
            f"Input winds are from agency '{agency}' ({int(hist['wind_avg_min'].iloc[-1])}-min mean). Models were "
            "trained on RSMC New Delhi 3-min winds; no conversion applied. Intensity output is NOT on the IMD scale "
            "and IMD category is withheld.")
    if int(s.frame["hist_len"].iat[0]) < cfg["history_steps"]:
        warnings.append(f"Short track history ({int(s.frame['hist_len'].iat[0])} x 6 h); uncertainty may be "
                        "underestimated.")

    leads = []
    for j, L in enumerate(s.leads):
        w_med = w0 + float(pw["dw"][0, j])
        w_lo, w_hi = max(0.0, w0 + float(wlo[0, j])), w0 + float(whi[0, j])
        entry = {
            "lead_h": L, "valid_time": (issue_time + pd.Timedelta(hours=L)).isoformat(),
            "lat": round(float(flat[j]), 3), "lon": round(float(flon[j]), 3),
            "track_radius_km_67": round(float(r67[j]), 1), "track_radius_km_90": round(float(r90[j]), 1),
            "cone_67": _cone(float(flat[j]), float(flon[j]), float(r67[j])),
            "wind_kt": round(w_med, 1), "wind_kt_90": [round(w_lo, 1), round(w_hi, 1)],
        }
        if agency == "newdelhi":
            entry["category"] = imd.classify(w_med).code
            entry["category_probabilities"] = {
                k: round(v, 3) for k, v in imd.category_probabilities({0.05: w_lo, 0.5: w_med, 0.95: w_hi}).items()}
        leads.append(entry)

    ri_p = float(reg["_ri"].predict_proba(s)[0])
    ri_cfg = config.load("imd_categories")["rapid_intensification"]
    return {
        "product": "EXPERIMENTAL_AI_FORECAST",
        "disclaimer": config.DISCLAIMER,
        "sid": str(s.frame["sid"].iat[0]), "name": str(s.frame["name"].iat[0]),
        "issue_time": issue_time.isoformat(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "initial": {"lat": lat0, "lon": lon0, "wind_kt": w0, "agency": agency,
                    "wind_avg_min": float(hist["wind_avg_min"].iloc[-1]),
                    "category": imd.classify(w0).code if agency == "newdelhi" else None},
        "leads": leads,
        "rapid_intensification": {
            "probability": round(ri_p, 3) if agency == "newdelhi" else None,
            "definition": f">= {ri_cfg['threshold_kt']} kt in {ri_cfg['window_h']} h (RSMC New Delhi winds)",
            "climatological_rate": round(reg["_ri"].base_rate, 4),
            "brier_skill": reg["_ri_skill"],
            "status": ("experimental - NO demonstrated skill on validation storms; treat as climatology"
                       if not reg["_ri_skill"] or (reg["_ri_skill"]["val"] or 0) <= 0.0
                       else "experimental - modest skill; see reports/evaluation.md"),
        },
        "uncertainty_method": f"split-conformal calibration on validation seasons {cfg['split']['val']}",
        "input_status": {"history_steps": int(s.frame["hist_len"].iat[0]), "satellite": "not_used",
                         "environment": ("SHIPS t=0 analysis" if not s.frame["env_missing"].iat[0] else
                                         "unavailable (model falls back to track-only behaviour)"),
                         "environment_values": {k: (None if pd.isna(s.frame[k].iat[0]) else
                                                    round(float(s.frame[k].iat[0]), 1))
                                                for k in ("env_shear_kt", "env_rh_700_500", "env_sst_c",
                                                          "env_ohc_clim", "env_mpi_kt")},
                         "warnings": warnings},
        "model": {"track": tl.meta["model_version"], "intensity": wl.meta["model_version"],
                  "ri": reg["ri_model"]["model_version"], "data_version": reg["data_version"]},
    }
