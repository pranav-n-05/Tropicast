"""Forecast verification metrics.

Track: great-circle error, along/cross-track decomposition (reference direction =
observed motion from issue position to verifying position), skill vs persistence
on the *same* homogeneous sample, storm-block bootstrap CIs.
Intensity: MAE, RMSE, bias of wind at lead (equivalently of wind change).
Uncertainty: empirical coverage and mean width/radius of calibrated intervals.
Probabilistic (RI): Brier score, Brier skill vs climatology, ROC AUC, reliability bins.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score

from tropicast.datasets.samples import SampleSet
from tropicast.geospatial.geo import along_cross_track_error
from tropicast.models.uncertainty import ConformalCalibrator, forecast_positions, track_errors_km


def _storm_bootstrap(values: np.ndarray, groups: np.ndarray, n: int = 500, seed: int = 0) -> tuple[float, float]:
    m = np.isfinite(values)
    values, groups = values[m], groups[m]
    if len(values) == 0:
        return float("nan"), float("nan")
    uniq = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        stats.append(values[np.concatenate([idx[g] for g in pick])].mean())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def _r(x: float, nd: int = 2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def evaluate(s: SampleSet, pred: dict, cal: ConformalCalibrator | None, ref_pred: dict | None = None,
             bootstrap: bool = True) -> dict:
    """Per-lead verification table for one model on one split."""
    err = track_errors_km(s, pred)
    ref_err = track_errors_km(s, ref_pred) if ref_pred is not None else None
    flat, flon = forecast_positions(s, pred)
    groups = s.frame["sid"].to_numpy()
    y_w = s.frame[s.target_cols("dw")].to_numpy(float)
    out = {"n_samples": int(len(s.frame)), "n_storms": int(s.frame["sid"].nunique()), "leads": {}}
    for j, L in enumerate(s.leads):
        e = err[:, j]
        m = np.isfinite(e)
        olat, olon = s.frame[f"lat_{L}"].to_numpy(float), s.frame[f"lon_{L}"].to_numpy(float)
        al, cr = along_cross_track_error(s.frame["lat"].to_numpy(), s.frame["lon"].to_numpy(), olat, olon,
                                         flat[:, j], flon[:, j])
        row = {
            "n": int(m.sum()),
            "track_err_mean_km": _r(np.nanmean(e)), "track_err_median_km": _r(np.nanmedian(e)),
            "track_err_p90_km": _r(np.nanpercentile(e[m], 90)) if m.any() else None,
            "along_bias_km": _r(np.nanmean(al)), "cross_bias_km": _r(np.nanmean(cr)),
            "along_mae_km": _r(np.nanmean(np.abs(al))), "cross_mae_km": _r(np.nanmean(np.abs(cr))),
        }
        if bootstrap:
            lo, hi = _storm_bootstrap(e, groups)
            row["track_err_mean_ci95_km"] = [_r(lo), _r(hi)]
        if ref_err is not None:
            both = m & np.isfinite(ref_err[:, j])
            row["track_skill_vs_persistence_pct"] = _r(100 * (1 - e[both].mean() / ref_err[both, j].mean()))
        we = pred["dw"][:, j] - y_w[:, j]
        mw = np.isfinite(we)
        row.update({"n_wind": int(mw.sum()), "wind_mae_kt": _r(np.nanmean(np.abs(we))),
                    "wind_rmse_kt": _r(np.sqrt(np.nanmean(we ** 2))), "wind_bias_kt": _r(np.nanmean(we))})
        if ref_pred is not None:
            re = np.abs(ref_pred["dw"][:, j] - y_w[:, j])
            both = mw & np.isfinite(re)
            if re[both].mean() > 0:
                row["wind_skill_vs_persistence_pct"] = _r(100 * (1 - np.abs(we[both]).mean() / re[both].mean()))
        if cal is not None:
            for q in cal.levels:
                rad = cal.track_radius(pred, q)[:, j]
                row[f"track_cov_{int(q*100)}"] = _r(np.mean(e[m] <= rad[m]), 3) if m.any() else None
                row[f"track_radius_mean_km_{int(q*100)}"] = _r(np.mean(rad[m])) if m.any() else None
                lo, hi = cal.wind_interval(pred, q)
                inside = (y_w[:, j] >= lo[:, j]) & (y_w[:, j] <= hi[:, j])
                row[f"wind_cov_{int(q*100)}"] = _r(np.mean(inside[mw]), 3) if mw.any() else None
                row[f"wind_width_mean_kt_{int(q*100)}"] = _r(np.mean((hi - lo)[mw, j])) if mw.any() else None
        out["leads"][str(L)] = row
    return out


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (p >= a) & (p < b if b < 1 else p <= b)
        if m.any():
            rows.append({"bin": [round(a, 2), round(b, 2)], "n": int(m.sum()),
                         "mean_forecast": _r(p[m].mean(), 3), "observed_freq": _r(y[m].mean(), 3)})
    return rows


def evaluate_probabilistic(y: np.ndarray, p: np.ndarray, base_rate: float) -> dict:
    """Brier score, Brier skill vs climatological base rate, ROC AUC, reliability."""
    y = y.astype(float)
    bs = float(np.mean((p - y) ** 2))
    bs_ref = float(np.mean((base_rate - y) ** 2))
    try:
        auc = float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")
    except ValueError:
        auc = float("nan")
    return {"n": int(len(y)), "n_positive": int(y.sum()), "event_rate": _r(y.mean(), 4),
            "brier": _r(bs, 4), "brier_climatology": _r(bs_ref, 4),
            "brier_skill": _r(1 - bs / bs_ref, 3) if bs_ref > 0 else None,
            "roc_auc": _r(auc, 3), "reliability": reliability(y, p)}
