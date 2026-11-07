"""Satellite study: nested season-block CV for multimodal ablation (prompt sec. 6).

Outer loop: 5 contiguous season blocks (train on 4, test on 1).
Inner loop (inside the 4 training blocks): 2-way split by block parity gives
out-of-fold CNN predictions for training rows, so the stage-2 (fusion) model
never sees CNN outputs that were fit on its own labels. The CNN used for the
outer test block is trained on all 4 training blocks. => no test-label leakage.

Fusion = feature concatenation into gradient boosting (the prompt's baseline;
attention/cross-attention fusion are deliberately not attempted with ~3.4k images).

Tasks
-----
A. intensity ESTIMATION at image time (wind_kt). Past wind is only used in the
   'full' configuration (as wind at t-6 h, the previous best-track value).
B. 24-h intensity CHANGE forecast (dw_24). Current wind is a state input in
   every configuration (otherwise configs are not comparable).
Also: IMD stage classification (from estimation) with confusion matrix/macro-F1,
and CNN interval coverage (normalised conformal from inner OOF residuals).
"""
from __future__ import annotations

import json
import logging
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import confusion_matrix, f1_score

from tropicast import config
from tropicast.datasets.samples import FEATURE_GROUPS
from tropicast.satellite.cnn import CNNEstimator
from tropicast.satellite.dataset import FOLDS, build_satset
from tropicast.satellite.features import IR_FEATURES, ir_features

log = logging.getLogger(__name__)
STAGES = [(-1, 34, "D/DD"), (34, 48, "CS"), (48, 64, "SCS"), (64, 999, "VSCS+")]
ENV_EST = [c for c in FEATURE_GROUPS["environment"] if c != "env_mpi_excess_kt"]  # excess uses current wind
TRACK_HIST = FEATURE_GROUPS["track"] + ["age_h", "dist2land", "month_sin", "month_cos", "is_as"]
SAT = ["cnn_mean", "cnn_sd"] + IR_FEATURES
SAT_T = ["cnn_prev6", "cnn_prev12", "cnn_d6"]
PAST_WIND = ["wind_prev6", "mw_2", "mw_3", "mw_4"]
INTENS_HIST = ["wind", "pres_filled", "pres_missing"] + [f"mw_{k}" for k in range(1, 5)]

EST_CONFIGS = {
    "climatology": None,
    "sat-only[IR features]": IR_FEATURES,
    "sat-only[CNN]": "cnn",
    "sat-only[CNN+IR features]": SAT,
    "env-only": ENV_EST + ["lat", "lon", "month_sin", "month_cos", "dist2land"],
    "sat+env": SAT + ENV_EST + ["lat", "lon"],
    "sat+env+temporal": SAT + SAT_T + ENV_EST + TRACK_HIST,
    "full (+previous best-track wind)": SAT + SAT_T + ENV_EST + TRACK_HIST + PAST_WIND,
    "reference: previous wind (t-6 h)": "prev",
}
FC_CONFIGS = {
    "persistence (no change)": None,
    "temporal-only": TRACK_HIST + INTENS_HIST,
    "env-only": FEATURE_GROUPS["environment"] + ["wind", "lat", "lon"],
    "sat-only": SAT + SAT_T + ["wind"],
    "sat+env": SAT + SAT_T + FEATURE_GROUPS["environment"] + ["wind", "lat", "lon"],
    "temporal+env": TRACK_HIST + INTENS_HIST + FEATURE_GROUPS["environment"],
    "full (sat+env+temporal)": SAT + SAT_T + TRACK_HIST + INTENS_HIST + FEATURE_GROUPS["environment"],
}


def _gbm(seed=0):
    return HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, learning_rate=0.05,
                                         max_leaf_nodes=15, min_samples_leaf=30, l2_regularization=1.0,
                                         early_stopping=True, validation_fraction=0.15, random_state=seed)


def _stage(w):
    w = np.asarray(w)
    return np.select([(w >= a) & (w < b) for a, b, _ in STAGES], [n for *_, n in STAGES], "D/DD")


def _cnn_feats(cnn: CNNEstimator, s) -> pd.DataFrame:
    p = cnn.predict(s.images, tta=4)
    out = pd.DataFrame({"cnn_mean": p["mean"], "cnn_sd": p["sd"]})
    for lag, arr in ((6, s.prev6), (12, s.prev12)):
        col = np.full(len(arr), np.nan, np.float32)
        ok = ~np.isnan(arr).reshape(len(arr), -1).all(1)
        if ok.any():
            col[ok] = cnn.predict(arr[ok], tta=4)["mean"]
        out[f"cnn_prev{lag}"] = col
    out["cnn_d6"] = out["cnn_mean"] - out["cnn_prev6"]
    return out


def _metrics(y, p):
    e = p - y
    return {"n": int(len(y)), "mae": round(float(np.mean(np.abs(e))), 2),
            "rmse": round(float(np.sqrt(np.mean(e ** 2))), 2), "bias": round(float(np.mean(e)), 2)}


def run(epochs: int = 15, members: int = 1, fast: bool = False) -> dict:
    t0 = time.time()
    s = build_satset()
    f = s.frame.copy()
    f["wind_prev6"] = f["wind"] - f["mw_1"]
    irf = pd.DataFrame(ir_features(s.images, s.prev6), columns=IR_FEATURES)
    f = pd.concat([f.reset_index(drop=True), irf], axis=1)
    if fast:
        epochs = 2
    oof = pd.DataFrame(index=f.index, columns=["cnn_mean", "cnn_sd", "cnn_prev6", "cnn_prev12", "cnn_d6"],
                       dtype=float)
    est_pred = {k: np.full(len(f), np.nan) for k in EST_CONFIGS}
    fc_pred = {k: np.full(len(f), np.nan) for k in FC_CONFIGS}
    cov90 = []
    for i in range(len(FOLDS)):
        tr_m, te_m = (f["fold"] != i).values, (f["fold"] == i).values
        trf = f[tr_m].reset_index(drop=True)
        # inner OOF CNN features for training rows
        inner = np.zeros((tr_m.sum(), 5))
        tr_s = s.subset(tr_m)
        par = (trf["fold"] % 2).values
        resid_norm = []
        for g in (0, 1):
            fit_m, pred_m = par != g, par == g
            cnn = CNNEstimator(members=members, epochs=epochs, seed=10 * i + g).fit(
                tr_s.images[fit_m], trf["wind"].values[fit_m])
            cf = _cnn_feats(cnn, tr_s.subset(pred_m))
            inner[pred_m] = cf.values
            resid_norm.append(np.abs(cf["cnn_mean"].values - trf["wind"].values[pred_m]) / cf["cnn_sd"].values)
        trf[["cnn_mean", "cnn_sd", "cnn_prev6", "cnn_prev12", "cnn_d6"]] = inner
        cnn_full = CNNEstimator(members=members, epochs=epochs, seed=100 + i).fit(tr_s.images, trf["wind"].values)
        tef = f[te_m].reset_index(drop=True)
        cf = _cnn_feats(cnn_full, s.subset(te_m))
        tef[cf.columns] = cf.values
        oof.loc[te_m, cf.columns] = cf.values
        # CNN 90 % interval: normalised conformal from inner OOF residuals
        q = float(np.quantile(np.concatenate(resid_norm), 0.9))
        inside = np.abs(tef["cnn_mean"] - tef["wind"]) <= q * tef["cnn_sd"]
        cov90.append({"fold": i, "q": round(q, 3), "coverage": round(float(inside.mean()), 3),
                      "mean_width_kt": round(float((2 * q * tef["cnn_sd"]).mean()), 1)})
        # stage 2
        for name, feats in EST_CONFIGS.items():
            if feats is None:
                p = np.full(len(tef), trf["wind"].mean())
            elif feats == "cnn":
                p = tef["cnn_mean"].values
            elif feats == "prev":
                p = tef["wind_prev6"].values
            else:
                m = _gbm(i).fit(trf[feats].to_numpy(float), trf["wind"].values)
                p = m.predict(tef[feats].to_numpy(float))
            est_pred[name][te_m] = p
        ok_tr = trf["dw_24"].notna().values
        for name, feats in FC_CONFIGS.items():
            if feats is None:
                p = np.zeros(len(tef))
            else:
                m = _gbm(i).fit(trf.loc[ok_tr, feats].to_numpy(float), trf.loc[ok_tr, "dw_24"].values)
                p = m.predict(tef[feats].to_numpy(float))
            fc_pred[name][te_m] = p
        log.info("outer fold %d done (%.0fs)", i, time.time() - t0)

    # ---- metrics (common subset where every modality exists) --------------
    common = (f["env_missing"] == 0).values & f["wind_prev6"].notna().values
    y = f["wind"].values
    est = {"all_rows": {}, "common_subset": {}}
    for name, p in est_pred.items():
        ok = np.isfinite(p)
        est["all_rows"][name] = _metrics(y[ok], p[ok]) if name.startswith(("sat-only", "climatology")) else None
        c = common & ok
        est["common_subset"][name] = _metrics(y[c], p[c])
        est["common_subset"][name]["per_fold_mae"] = [
            round(float(np.mean(np.abs(p[c & (f["fold"] == k).values] - y[c & (f["fold"] == k).values]))), 2)
            if (c & (f["fold"] == k).values).any() else None for k in range(len(FOLDS))]
    est["all_rows"] = {k: v for k, v in est["all_rows"].items() if v}
    yd = f["dw_24"].values
    fcm = {}
    cfc = common & np.isfinite(yd)
    for name, p in fc_pred.items():
        fcm[name] = _metrics(yd[cfc], p[cfc])
        ri_t = config.load("imd_categories")["rapid_intensification"]["threshold_kt"]
        fcm[name]["ri_hit_rate_of_events"] = round(float(np.mean(p[cfc][yd[cfc] >= ri_t] >= ri_t)), 3) \
            if (yd[cfc] >= ri_t).any() else None
    # stage classification
    cls = {}
    labels = [n for *_, n in STAGES]
    for name in ("sat-only[CNN]", "sat+env+temporal", "full (+previous best-track wind)"):
        p = est_pred[name]
        c = common & np.isfinite(p)
        yt, yp = _stage(y[c]), _stage(p[c])
        cls[name] = {"accuracy": round(float(np.mean(yt == yp)), 3),
                     "macro_f1": round(float(f1_score(yt, yp, labels=labels, average="macro")), 3),
                     "labels": labels, "confusion_matrix": confusion_matrix(yt, yp, labels=labels).tolist()}
    report = {
        "generated_utc": pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "runtime_s": round(time.time() - t0, 1), "fast_mode": fast,
        "data": {"images": int(len(f)), "storms": int(f["sid"].nunique()),
                 "seasons": [int(f["season"].min()), int(f["season"].max())],
                 "common_subset_rows": int(common.sum()), "folds": FOLDS,
                 "satellites": f["sat"].value_counts().to_dict(),
                 "per_fold_rows": f["fold"].value_counts().sort_index().to_dict()},
        "cnn": {"epochs": epochs, "members": members, "interval90": cov90},
        "estimation": est, "forecast_dw24": fcm, "stage_classification": cls,
        "notes": [
            "Labels: RSMC New Delhi 3-min winds. Imagery: HURSAT-B1 v06 IRWIN, best (lowest VZA) satellite.",
            "Satellite archive ends 2015, so these results are a separate hindcast study, not the live system.",
            "Common subset = rows with SHIPS environment and a t-6 h best-track wind (1990-2015).",
            "Explainability (Grad-CAM) is an interpretive aid, not proof of physical causation.",
        ],
    }
    out = config.reports_dir() / "satellite_evaluation.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    _write_md(report)
    oof.assign(sid=f["sid"], time=f["time"]).to_pickle(config.artifacts_dir() / "satellite_oof.pkl")
    return report


def _write_md(r: dict) -> None:
    L = ["# Satellite study (auto-generated)", "",
         f"Generated {r['generated_utc']}, runtime {r['runtime_s']} s, fast_mode={r['fast_mode']}. "
         "Every number below is computed by `tropicast satellite`.", "",
         f"- Images: {r['data']['images']} from {r['data']['storms']} storms, seasons {r['data']['seasons']}",
         f"- Nested CV over season blocks {r['data']['folds']}",
         f"- Common subset (all modalities present): {r['data']['common_subset_rows']} rows", "",
         "## A. Intensity estimation (wind at image time, kt)", "",
         "| configuration | n | MAE | RMSE | bias | MAE per fold |", "|---|---|---|---|---|---|"]
    for k, v in r["estimation"]["common_subset"].items():
        L.append(f"| {k} | {v['n']} | {v['mae']} | {v['rmse']} | {v['bias']} | {v['per_fold_mae']} |")
    L += ["", "Satellite-only on all rows (no environment requirement):", "",
          "| configuration | n | MAE | RMSE | bias |", "|---|---|---|---|---|"]
    for k, v in r["estimation"]["all_rows"].items():
        L.append(f"| {k} | {v['n']} | {v['mae']} | {v['rmse']} | {v['bias']} |")
    L += ["", "CNN 90 % interval (normalised conformal, calibrated on inner out-of-fold residuals):", "",
          "| fold | coverage | mean width kt |", "|---|---|---|"]
    for c in r["cnn"]["interval90"]:
        L.append(f"| {c['fold']} | {c['coverage']} | {c['mean_width_kt']} |")
    L += ["", "## B. 24-h intensity change forecast (kt), common subset", "",
          "| configuration | n | MAE | RMSE | bias | RI events predicted >= threshold |", "|---|---|---|---|---|---|"]
    for k, v in r["forecast_dw24"].items():
        L.append(f"| {k} | {v['n']} | {v['mae']} | {v['rmse']} | {v['bias']} | {v['ri_hit_rate_of_events']} |")
    L += ["", "## C. IMD stage classification from estimated intensity (common subset)", ""]
    for k, v in r["stage_classification"].items():
        L += [f"**{k}**: accuracy {v['accuracy']}, macro-F1 {v['macro_f1']}", "",
              "| true \\ predicted | " + " | ".join(v["labels"]) + " |", "|---|" + "---|" * len(v["labels"])]
        for lab, row in zip(v["labels"], v["confusion_matrix"]):
            L.append(f"| {lab} | " + " | ".join(map(str, row)) + " |")
        L.append("")
    L += ["## Notes"] + [f"- {n}" for n in r["notes"]]
    (config.reports_dir() / "satellite_evaluation.md").write_text("\n".join(L) + "\n")
