"""Render ``reports/evaluation.json`` as Markdown. Numbers are copied, never edited."""
from __future__ import annotations

from pathlib import Path


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, list):
        return f"[{_fmt(v[0])}, {_fmt(v[1])}]"
    return f"{v}"


def _table(results: dict, cols: list[tuple[str, str]], models: list[str]) -> str:
    leads = list(next(iter(results.values()))["leads"])
    lines = ["| model | lead h | " + " | ".join(c[1] for c in cols) + " |",
             "|---|---|" + "---|" * len(cols)]
    for m in models:
        for L in leads:
            r = results[m]["leads"][L]
            lines.append(f"| {m} | {L} | " + " | ".join(_fmt(r.get(c[0])) for c in cols) + " |")
    return "\n".join(lines)


def write_markdown(rep: dict, path: Path) -> None:
    test, val = rep["results"]["test"], rep["results"]["val"]
    models = list(test)
    main = [m for m in models if "[" not in m]
    abl = rep.get("ablation_models", [])
    sel = rep["selection"]
    ds = rep["dataset"]
    md = [
        "# Evaluation report (auto-generated)",
        "",
        f"Generated {rep['generated_utc']} - runtime {rep['runtime_s']} s - fast_mode={rep['fast_mode']}.",
        "All numbers below were computed by `tropicast train`; none are hand-entered.",
        "",
        "+pr = model predicts correction to persistence extrapolation.",
        "",
        "> Experimental research output. Not an official forecast. Labels: RSMC New Delhi (IMD) best track, "
        "3-min mean winds, via IBTrACS v04r01.",
        "",
        "## Dataset",
        f"- Data version `{ds['manifest']['data_version']}`; raw sha256 `{ds['manifest']['raw_sha256'][:16]}...`",
        f"- Storms (all agencies, in bbox): {ds['manifest']['storms']}; seasons {ds['manifest']['seasons']}",
        "",
        "| split | samples | storms | seasons | RI valid | RI positive | RI rate |",
        "|---|---|---|---|---|---|---|",
    ]
    for k, v in ds["splits"].items():
        md.append(f"| {k} | {v['samples']} | {v['storms']} | {v['seasons']} | {v['ri_valid']} | "
                  f"{v['ri_positive']} | {v['ri_rate']} |")
    md += [
        "",
        "Splits are by season (" + ", ".join(f"{k} {v[0]}-{v[1]}" for k, v in rep["split"].items())
        + ") and are asserted event-disjoint. Training uses every 3-hourly issue time; validation and test "
        "use synoptic (00/06/12/18 UTC) issues only.",
        "",
        f"## Selection (on validation only)\n- Track model: **{sel['track']}**\n- Intensity model: "
        f"**{sel['intensity']}**\n- RI model: **{sel['ri']}** (experimental)",
        "",
        "## Test - track error",
        "Skill = 1 - error/persistence error on the same samples. CI = 95 % storm-block bootstrap.",
        "",
        _table(test, [("n", "n"), ("track_err_mean_km", "mean km"), ("track_err_mean_ci95_km", "95% CI"),
                      ("track_err_median_km", "median km"), ("along_bias_km", "along bias"),
                      ("cross_bias_km", "cross bias"), ("track_skill_vs_persistence_pct", "skill %")], main),
        "",
        "## Test - intensity (max sustained wind)",
        "",
        _table(test, [("n_wind", "n"), ("wind_mae_kt", "MAE kt"), ("wind_rmse_kt", "RMSE kt"),
                      ("wind_bias_kt", "bias kt"), ("wind_skill_vs_persistence_pct", "skill %")], main),
        "",
        "## Test - calibration of uncertainty (calibrated on validation)",
        "Nominal coverage 67 % and 90 %. Values near nominal = well calibrated.",
        "",
        _table(test, [("track_cov_67", "track cov67"), ("track_radius_mean_km_67", "r67 km"),
                      ("track_cov_90", "track cov90"), ("track_radius_mean_km_90", "r90 km"),
                      ("wind_cov_90", "wind cov90"), ("wind_width_mean_kt_90", "width90 kt")],
               [m for m in main if m != "persistence"]),
        "",
        "## Ablation (available modalities only; GBM)",
        "track = position + motion history; +intensity = wind/pressure history; full adds context "
        "(distance to land, month, storm age, sub-basin).",
        "",
        _table(test, [("track_err_mean_km", "track km"), ("wind_mae_kt", "wind MAE kt")], abl),
        "",
        "## Environment ablation (homogeneous test subset with SHIPS predictors, 2019-2021)",
        "env-only = position + current wind + SHIPS t=0 environment (no history). temporal = track + intensity "
        "history. Same samples for every row.",
        "",
        _table(rep["results"]["test_env"], [("n", "n"), ("track_err_mean_km", "track km"),
                                            ("track_skill_vs_persistence_pct", "track skill %"),
                                            ("wind_mae_kt", "wind MAE kt"),
                                            ("wind_skill_vs_persistence_pct", "wind skill %")],
               [m for m in rep.get("env_ablation_models", []) if m in rep["results"]["test_env"]]),
        "",
        "## Rapid intensification (EXPERIMENTAL)",
        "",
        "| split | model | n | positives | Brier | Brier clim. | BSS | AUC |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for split_name, d in rep["rapid_intensification"].items():
        for k, r in d.items():
            md.append(f"| {split_name} | {k} | {r['n']} | {r['n_positive']} | {r['brier']} | "
                      f"{r['brier_climatology']} | {r['brier_skill']} | {r['roc_auc']} |")
    md += ["", "## Not yet evaluated"] + [f"- **{k}**: {v}" for k, v in rep["not_evaluated"].items()]
    md += ["", "## Validation tables", "", _table(val, [("track_err_mean_km", "track km"),
                                                       ("wind_mae_kt", "wind MAE kt")], models)]
    path.write_text("\n".join(md) + "\n")
