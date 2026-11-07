"""Split-conformal calibration of track and intensity uncertainty.

Calibration uses the *validation* storms only (never test). For every lead:

* Track: nonconformity score = great-circle error (km), optionally divided by the
  model's own spread (normalised conformal). The calibrated radius for coverage
  ``q`` is the finite-sample-corrected ``q``-quantile of scores (x spread).
* Intensity: conformalised quantile regression (Romano et al., 2019) when the model
  emits lower/upper quantiles; otherwise absolute-residual conformal.

Guarantee is marginal coverage under exchangeability between validation and
future storms - an assumption, not a fact (climate trends, agency practice changes).
"""
from __future__ import annotations

import numpy as np

from tropicast.datasets.samples import SampleSet
from tropicast.geospatial.geo import haversine_km, km_to_displacement


def _conf_q(scores: np.ndarray, q: float) -> float:
    s = np.sort(scores[np.isfinite(scores)])
    n = len(s)
    if n == 0:
        return float("nan")
    k = min(n - 1, int(np.ceil((n + 1) * q)) - 1)
    return float(s[max(k, 0)])


def forecast_positions(s: SampleSet, pred: dict) -> tuple[np.ndarray, np.ndarray]:
    lat0 = s.frame["lat"].to_numpy()[:, None]
    lon0 = s.frame["lon"].to_numpy()[:, None]
    return km_to_displacement(lat0, lon0, pred["dx"], pred["dy"])


def track_errors_km(s: SampleSet, pred: dict) -> np.ndarray:
    flat, flon = forecast_positions(s, pred)
    olat = s.frame[[f"lat_{L}" for L in s.leads]].to_numpy(float)
    olon = s.frame[[f"lon_{L}" for L in s.leads]].to_numpy(float)
    return haversine_km(olat, olon, flat, flon)


class ConformalCalibrator:
    def __init__(self, levels=(0.67, 0.9)):
        self.levels = tuple(levels)
        self.track: dict[float, list[float]] = {}
        self.track_normalised = False
        self.wind: dict[float, list[float]] = {}
        self.wind_mode = "residual"

    def fit(self, val: SampleSet, pred: dict) -> "ConformalCalibrator":
        err = track_errors_km(val, pred)
        sig = pred.get("track_sigma")
        self.track_normalised = sig is not None
        scores = err / np.maximum(sig, 1.0) if sig is not None else err
        self.track = {q: [_conf_q(scores[:, j], q) for j in range(len(val.leads))] for q in self.levels}
        y = val.frame[val.target_cols("dw")].to_numpy(float)
        if "dw_lo" in pred:
            self.wind_mode = "cqr"
            # CQR uses one nominal level; rescale raw 90 % band to each target level is not
            # valid, so CQR is applied at 0.9 and residual conformal for other levels.
            e = np.maximum(pred["dw_lo"] - y, y - pred["dw_hi"])
            self.wind[0.9] = [_conf_q(e[:, j], 0.9) for j in range(len(val.leads))]
        r = np.abs(y - pred["dw"])
        for q in self.levels:
            if not (self.wind_mode == "cqr" and q == 0.9):
                self.wind[q] = [_conf_q(r[:, j], q) for j in range(len(val.leads))]
        return self

    def track_radius(self, pred: dict, q: float) -> np.ndarray:
        base = np.array(self.track[q])[None, :]
        if self.track_normalised:
            return base * np.maximum(pred["track_sigma"], 1.0)
        return np.repeat(base, len(pred["dx"]), axis=0)

    def wind_interval(self, pred: dict, q: float) -> tuple[np.ndarray, np.ndarray]:
        adj = np.array(self.wind[q])[None, :]
        if self.wind_mode == "cqr" and q == 0.9:
            return pred["dw_lo"] - adj, pred["dw_hi"] + adj
        return pred["dw"] - adj, pred["dw"] + adj

    def state(self) -> dict:
        return {"levels": self.levels, "track": {str(k): v for k, v in self.track.items()},
                "track_normalised": self.track_normalised,
                "wind": {str(k): v for k, v in self.wind.items()}, "wind_mode": self.wind_mode}

    @classmethod
    def from_state(cls, st: dict) -> "ConformalCalibrator":
        c = cls(st["levels"])
        c.track = {float(k): v for k, v in st["track"].items()}
        c.wind = {float(k): v for k, v in st["wind"].items()}
        c.track_normalised, c.wind_mode = st["track_normalised"], st["wind_mode"]
        return c
