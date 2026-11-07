"""Train, calibrate, evaluate, select and register forecast models.

Protocol (no test-set peeking):
1. Fit every candidate on TRAIN storms.
2. Calibrate uncertainty (conformal) on VAL storms.
3. Select the operational track model and intensity model by VAL mean error.
4. Report TEST metrics for all candidates (selection already frozen).
Every number in reports/ is produced by this code from the actual run.
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from datetime import datetime, timezone

import numpy as np
import torch

from tropicast import config
from tropicast.datasets import build
from tropicast.datasets.samples import ALL_FEATURES_ENV, FEATURE_GROUPS, build_samples, split
from tropicast.evaluation.metrics import evaluate, evaluate_probabilistic
from tropicast.models.baselines import GBMModel, PersistenceModel, PersistenceResidual, RidgeModel
from tropicast.models.gru import STATIC, GRUEnsemble
from tropicast.models.rapid_intensification import RIModel, ri_labels
from tropicast.models.uncertainty import ConformalCalibrator

log = logging.getLogger(__name__)


def _mean_over_leads(ev: dict, key: str) -> float:
    vals = [r[key] for r in ev["leads"].values() if r.get(key) is not None]
    return float(np.mean(vals)) if vals else float("inf")


def _class_stats(parts) -> dict:
    out = {}
    for name, s in parts.items():
        y, v = ri_labels(s)
        f = s.frame
        out[name] = {
            "samples": int(len(f)), "storms": int(f["sid"].nunique()),
            "seasons": [int(f["season"].min()), int(f["season"].max())] if len(f) else None,
            "target_missing_rate": {str(L): round(float(f[f"dx_{L}"].isna().mean()), 3) for L in s.leads},
            "ri_valid": int(v.sum()), "ri_positive": int(y[v].sum()),
            "ri_rate": round(float(y[v].mean()), 4) if v.any() else None,
            "intensity_at_issue_kt": {k: int(n) for k, n in
                                      f["wind"].describe()[["min", "50%", "max"]].round(0).items()},
        }
    return out


def run(fast: bool = False, refresh: bool = False) -> dict:
    t_start = time.time()
    cfg = config.load("training")
    np.random.seed(cfg["seed"])
    torch.manual_seed(cfg["seed"])
    man = build.build_processed(refresh=refresh)
    samples = build_samples(build.load_tracks("tracks"), agency="newdelhi", cfg=cfg, env=build.load_env())
    parts = split(samples, cfg)
    # train on all (3-hourly) issue times; verify/calibrate on synoptic issues only
    tr = parts["train"]
    va_all = parts["val"]
    va = va_all.subset(va_all.frame["synoptic"].values)
    te = parts["test"].subset(parts["test"].frame["synoptic"].values)
    parts = {"train": tr, "val": va, "test": te}
    log.info("samples train=%d val=%d test=%d", len(tr.frame), len(va.frame), len(te.frame))

    gru_cfg = dict(cfg["gru"])
    if fast:
        gru_cfg.update(epochs=8, ensemble=2)
    it = 100 if fast else 300
    q = tuple(cfg["quantiles"])
    candidates = {
        "persistence": PersistenceModel(),
        "ridge+pr": PersistenceResidual(RidgeModel()),
        "gbm": GBMModel(quantiles=q, seed=cfg["seed"], max_iter=it),
        "gbm+pr": PersistenceResidual(GBMModel(quantiles=q, seed=cfg["seed"], max_iter=it)),
        "gru_ensemble+pr": PersistenceResidual(GRUEnsemble(seed=cfg["seed"], **gru_cfg)),
        "gbm+pr+env": PersistenceResidual(GBMModel(features=ALL_FEATURES_ENV, quantiles=q, seed=cfg["seed"],
                                                   max_iter=it)),
        "gru_ensemble+pr+env": PersistenceResidual(GRUEnsemble(
            seed=cfg["seed"], static=STATIC + FEATURE_GROUPS["environment"], **gru_cfg)),
    }
    ablations = {
        "gbm+pr[track]": PersistenceResidual(GBMModel(features=FEATURE_GROUPS["track"], quantiles=q,
                                                      seed=cfg["seed"], max_iter=it)),
        "gbm+pr[track+intensity]": PersistenceResidual(GBMModel(
            features=FEATURE_GROUPS["track"] + FEATURE_GROUPS["intensity"], quantiles=q, seed=cfg["seed"],
            max_iter=it)),
        # environment ablation (prompt sec. 6): env-only uses t0 state (position, wind) + SHIPS predictors
        "gbm[env-only]": GBMModel(features=["lat", "lon", "wind"] + FEATURE_GROUPS["environment"], quantiles=q,
                                  seed=cfg["seed"], max_iter=it),
        "gbm+pr[temporal+env]": PersistenceResidual(GBMModel(
            features=FEATURE_GROUPS["track"] + FEATURE_GROUPS["intensity"] + FEATURE_GROUPS["environment"],
            quantiles=q, seed=cfg["seed"], max_iter=it)),
    }

    results: dict = {"val": {}, "test": {}, "test_env": {}}
    env_mask = (te.frame["env_missing"] == 0).values
    te_env = te.subset(env_mask)
    fitted: dict = {}
    preds_val, preds_test = {}, {}
    for name, model in {**candidates, **ablations}.items():
        t0 = time.time()
        model.fit(tr, va_all)
        pv, pt = model.predict(va), model.predict(te)
        cal = ConformalCalibrator().fit(va, pv)
        fitted[name] = (model, cal)
        preds_val[name], preds_test[name] = pv, pt
        log.info("fitted %s in %.1fs", name, time.time() - t0)

    for name, (model, cal) in fitted.items():
        results["val"][name] = evaluate(va, preds_val[name], cal, preds_val["persistence"], bootstrap=False)
        results["test"][name] = evaluate(te, preds_test[name], cal, preds_test["persistence"])
        sub = {k: v[env_mask] for k, v in preds_test[name].items() if isinstance(v, np.ndarray)}
        ref = {k: v[env_mask] for k, v in preds_test["persistence"].items()}
        results["test_env"][name] = evaluate(te_env, sub, cal, ref, bootstrap=False)

    sel_pool = list(candidates)
    track_sel = min(sel_pool, key=lambda n: _mean_over_leads(results["val"][n], "track_err_mean_km"))
    wind_sel = min(sel_pool, key=lambda n: _mean_over_leads(results["val"][n], "wind_mae_kt"))

    # RI (experimental)
    ri_res = {}
    ri_models = {}
    for key, kind, feats in (("logistic", "logistic", None), ("gbm", "gbm", None),
                             ("logistic+env", "logistic", ALL_FEATURES_ENV), ("gbm+env", "gbm", ALL_FEATURES_ENV)):
        m = RIModel(kind, seed=cfg["seed"], features=feats).fit(tr)
        m.name = f"ri_{key}"
        kind = key
        ri_models[kind] = m
        for nm, s in (("val", va), ("test", te)):
            y, v = ri_labels(s)
            ri_res.setdefault(nm, {})[kind] = evaluate_probabilistic(y[v], m.predict_proba(s)[v], m.base_rate)
    ri_sel = min(ri_models, key=lambda k: ri_res["val"][k]["brier"])

    # registry
    data_version = man["data_version"]
    cfg_sha = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    art = config.artifacts_dir()
    run_dir = art / f"run-{stamp}"
    run_dir.mkdir(parents=True)

    def save(name: str) -> dict:
        model, cal = fitted[name]
        path = run_dir / f"{name}.pkl"
        base = getattr(model, "base", model)
        if isinstance(base, GRUEnsemble):
            torch.save({"kind": "gru", "residual": base is not model, "state": base.state(),
                        "cal": cal.state()}, path)
        else:
            with path.open("wb") as fh:
                pickle.dump({"kind": "sklearn", "model": model, "cal": cal.state()}, fh)
        return {"model_name": name, "model_version": f"{name}-{data_version}-{cfg_sha}-{stamp}",
                "path": str(path.relative_to(config.PROJECT_ROOT))}

    with (run_dir / "ri.pkl").open("wb") as fh:
        pickle.dump(ri_models[ri_sel], fh)
    registry = {
        "created_utc": stamp,
        "data_version": data_version,
        "training_config_sha": cfg_sha,
        "fast_mode": fast,
        "track_model": save(track_sel),
        "intensity_model": save(wind_sel) if wind_sel != track_sel else None,
        "reference_model": save("persistence"),
        "ri_model": {"model_name": f"ri_{ri_sel}",
                     "model_version": f"ri_{ri_sel}-{data_version}-{cfg_sha}-{stamp}",
                     "path": str((run_dir / "ri.pkl").relative_to(config.PROJECT_ROOT)), "status": "experimental"},
        "selection_rule": "lowest validation mean error averaged over leads",
        "split": cfg["split"],
        "leads_h": cfg["lead_times_h"],
    }
    if registry["intensity_model"] is None:
        registry["intensity_model"] = dict(registry["track_model"])
    (art / "registry.json").write_text(json.dumps(registry, indent=2))

    report = {
        "generated_utc": stamp, "runtime_s": round(time.time() - t_start, 1), "fast_mode": fast,
        "dataset": {"manifest": man, "splits": _class_stats(parts)},
        "selection": {"track": track_sel, "intensity": wind_sel, "ri": f"ri_{ri_sel}"},
        "split": cfg["split"],
        "ablation_models": ["gbm+pr[track]", "gbm+pr[track+intensity]", "gbm+pr"],
        "env_ablation_models": ["persistence", "gbm[env-only]", "gbm+pr[track+intensity]", "gbm+pr[temporal+env]",
                                "gbm+pr", "gbm+pr+env", "gru_ensemble+pr", "gru_ensemble+pr+env"],
        "results": results, "rapid_intensification": ri_res, "registry": registry,
        "not_evaluated": {
            "satellite modalities in the 72 h forecast": "Not combined here - HURSAT ends 2015, so the "
                "satellite ablation is a separate study (reports/satellite_evaluation.md).",
        },
    }
    rep_dir = config.reports_dir()
    (rep_dir / "evaluation.json").write_text(json.dumps(report, indent=2, default=str))
    from tropicast.evaluation.report import write_markdown
    write_markdown(report, rep_dir / "evaluation.md")
    log.info("done in %.1fs; track=%s intensity=%s", time.time() - t_start, track_sel, wind_sel)
    return report
