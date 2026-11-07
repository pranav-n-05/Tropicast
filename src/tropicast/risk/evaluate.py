"""Verification of 72-h landfall probability on unseen test seasons.

For each test storm and each 12-hourly synoptic issue time with the centre over
water, issue a forecast with the registered models, compute P(landfall <= 72 h)
from member tracks, and compare with the observed track (IBTrACS DIST2LAND).
Scores: Brier, Brier skill vs climatology (training-period base rate),
ROC AUC, reliability table.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from tropicast import config
from tropicast.datasets import build
from tropicast.evaluation.metrics import evaluate_probabilistic
from tropicast.inference.forecast import forecast_storm
from tropicast.risk.landfall import exposure, observed_landfall

log = logging.getLogger(__name__)


def _cases(tracks: pd.DataFrame, a: int, b: int, every_h: int = 12):
    t = tracks[(tracks["agency"] == "newdelhi") & tracks["season"].between(a, b) & tracks["wind_kt"].notna()]
    for sid, g in t.groupby("sid"):
        for t0 in g["time"]:
            if t0.hour % every_h == 0:
                yield sid, g, t0


def run(members: int = 200) -> dict:
    cfg = config.load("training")
    tracks = build.load_tracks("tracks")
    env = build.load_env()
    # climatological base rate from training seasons (observed outcomes only, no model)
    base = [observed_landfall(g, t0) for _, g, t0 in _cases(tracks, *cfg["split"]["train"])]
    base = [x for x in base if x is not None]
    rate = float(np.mean(base))
    rows = []
    for sid, g, t0 in _cases(tracks, *cfg["split"]["test"]):
        obs = observed_landfall(g, t0)
        if obs is None:
            continue
        try:
            fc = forecast_storm(g, t0, env=env)
        except ValueError:
            continue
        ex = exposure(fc, n=members)
        if ex["p_landfall_72h"] is None:
            continue
        top = ex["landfall_regions"][0]["region"] if ex["landfall_regions"] else None
        rows.append({"sid": sid, "t0": t0, "p": ex["p_landfall_72h"], "obs": int(obs), "top_region": top})
    df = pd.DataFrame(rows)
    res = evaluate_probabilistic(df["obs"].to_numpy(), df["p"].to_numpy(), rate)
    res.update({"climatology_rate_train": round(rate, 4), "test_storms": int(df["sid"].nunique()),
                "members": members, "issue_every_h": 12,
                "definition": "landfall = observed centre moves from water (DIST2LAND>0) to land within 72 h"})
    (config.reports_dir() / "landfall_evaluation.json").write_text(json.dumps(res, indent=2, default=str))
    return res
