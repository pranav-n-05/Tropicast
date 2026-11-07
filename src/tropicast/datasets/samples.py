"""Sample construction for track and intensity forecasting.

Sample definition
-----------------
One sample = one storm at one synoptic issue time ``t0`` (6-hourly) where the
storm is at least depression strength (``min_wind_kt``). Inputs use only data
at or before ``t0``. Targets are, for each lead ``L`` in ``lead_times_h``:

* ``dx_L``, ``dy_L`` : east/north displacement (km) from the ``t0`` position
* ``dw_L``          : wind change (kt) from ``t0`` (same agency, no conversion)

A target is NaN when the storm has no observation at ``t0 + L`` (dissipated or
gap) and is masked in training/evaluation. Storms are kept only if all used
rows come from a single agency; training uses RSMC New Delhi (3-min) only.

Splits are by season, which makes them event-disjoint (no storm crosses a
season boundary in IBTrACS NI SIDs) - this is asserted, not assumed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tropicast import config
from tropicast.geospatial.geo import displacement_to_km

FEATURE_GROUPS = {
    # ablation groups available without satellite/reanalysis data
    "track": ["lat", "lon", "hist_len"] + [f"mx_{k}" for k in range(1, 5)] + [f"my_{k}" for k in range(1, 5)],
    "intensity": ["wind", "pres_filled", "pres_missing"] + [f"mw_{k}" for k in range(1, 5)],
    "context": ["dist2land", "month_sin", "month_cos", "age_h", "is_as"],
}
from tropicast.ingestion.ships import ENV_FEATURES  # noqa: E402

ALL_FEATURES = FEATURE_GROUPS["track"] + FEATURE_GROUPS["intensity"] + FEATURE_GROUPS["context"]
FEATURE_GROUPS["environment"] = ENV_FEATURES + ["env_missing"]
ALL_FEATURES_ENV = ALL_FEATURES + FEATURE_GROUPS["environment"]
SEQ_FEATURES = ["mx", "my", "mw", "wind", "lat", "lon"]  # per-step features for the GRU


@dataclass
class SampleSet:
    frame: pd.DataFrame          # one row per sample: ids, features, targets
    seq: np.ndarray              # (n, history_steps + 1, len(SEQ_FEATURES)) GRU input
    leads: list[int]

    def target_cols(self, kind: str) -> list[str]:
        return [f"{kind}_{L}" for L in self.leads]

    def subset(self, mask: np.ndarray) -> "SampleSet":
        mask = np.asarray(mask)
        return SampleSet(self.frame[mask].reset_index(drop=True), self.seq[mask], self.leads)


def _storm_samples(g: pd.DataFrame, cfg: dict, leads: list[int]) -> tuple[list[dict], list[np.ndarray]]:
    step = cfg["timestep_h"]
    H = cfg["history_steps"]
    g = g.set_index("time").sort_index()
    times = g.index
    first_time = times[0]
    rows, seqs = [], []
    lookup = g[["lat", "lon", "wind_kt"]]
    for t0 in times:
        cur = g.loc[t0]
        if not (cur["wind_kt"] >= cfg["min_wind_kt"]):
            continue
        # history positions at t0 - k*step, contiguous only
        hist = [t0]
        for k in range(1, H + 1):
            tk = t0 - pd.Timedelta(hours=k * step)
            if tk in lookup.index:
                hist.append(tk)
            else:
                break
        if len(hist) < 2:  # need at least one motion vector
            continue
        hp = lookup.loc[hist[::-1]]  # oldest -> newest
        dx, dy = displacement_to_km(hp["lat"].values[:-1], hp["lon"].values[:-1],
                                    hp["lat"].values[1:], hp["lon"].values[1:])
        dw = np.diff(hp["wind_kt"].values)
        # newest motion first; pad by repeating oldest available motion
        mx = list(dx[::-1]) + [dx[0]] * (H - len(dx))
        my = list(dy[::-1]) + [dy[0]] * (H - len(dy))
        mw = list(np.nan_to_num(dw[::-1])) + [float(np.nan_to_num(dw[0]))] * (H - len(dw))
        pres = cur["pres_hpa"]
        rec = {
            "synoptic": bool(t0.hour % 6 == 0 and t0.minute == 0),
            "sid": g["sid"].iat[0], "season": int(g["season"].iat[0]), "name": g["name"].iat[0],
            "t0": t0, "agency": cur["agency"],
            "lat": cur["lat"], "lon": cur["lon"], "wind": cur["wind_kt"],
            "pres_filled": pres if pd.notna(pres) else 1004.0, "pres_missing": float(pd.isna(pres)),
            "hist_len": len(dx), "dist2land": cur["dist2land_km"],
            "month_sin": np.sin(2 * np.pi * t0.month / 12), "month_cos": np.cos(2 * np.pi * t0.month / 12),
            "age_h": (t0 - first_time).total_seconds() / 3600, "is_as": float(cur["subbasin"] == "AS"),
        }
        for k in range(H):
            rec[f"mx_{k+1}"], rec[f"my_{k+1}"], rec[f"mw_{k+1}"] = mx[k], my[k], mw[k]
        for L in leads:
            tl = t0 + pd.Timedelta(hours=L)
            if tl in lookup.index and pd.notna(lookup.at[tl, "lat"]):
                x, y = displacement_to_km(cur["lat"], cur["lon"], lookup.at[tl, "lat"], lookup.at[tl, "lon"])
                rec[f"dx_{L}"], rec[f"dy_{L}"] = float(x), float(y)
                rec[f"lat_{L}"], rec[f"lon_{L}"] = lookup.at[tl, "lat"], lookup.at[tl, "lon"]
                w = lookup.at[tl, "wind_kt"]
                rec[f"dw_{L}"] = float(w - cur["wind_kt"]) if pd.notna(w) else np.nan
            else:
                for k in ("dx", "dy", "dw", "lat", "lon"):
                    rec[f"{k}_{L}"] = np.nan
        # GRU sequence, oldest -> newest. Step k (1 = newest) ends at t0-(k-1)*step;
        # wind at the end of step k = wind(t0) - sum of later wind changes.
        seq = []
        for k in range(H, 0, -1):
            wind_end = cur["wind_kt"] - float(np.sum(mw[: k - 1]))
            seq.append([mx[k - 1], my[k - 1], mw[k - 1], wind_end, cur["lat"], cur["lon"]])
        seq = np.asarray(seq)
        rows.append(rec)
        seqs.append(seq.astype(np.float32))
    return rows, seqs


def attach_env(frame: pd.DataFrame, env: pd.DataFrame | None) -> pd.DataFrame:
    """Left-join t=0 environmental predictors on (sid, t0); flag missing rows.

    ``env_mpi_excess_kt`` is recomputed with the sample's own (IMD) wind so no
    other agency's intensity leaks into the features.
    """
    f = frame.drop(columns=[c for c in ENV_FEATURES + ["env_missing"] if c in frame.columns])
    if env is not None and len(env) and len(f):
        # backward as-of join within 3 h: off-synoptic issues reuse the previous analysis,
        # never a later one (no future information).
        e = env.rename(columns={"time": "t0"})[["sid", "t0"] + [c for c in ENV_FEATURES if c in env.columns]]
        e = e.sort_values("t0")
        f["_ord"] = np.arange(len(f))
        f = pd.merge_asof(f.sort_values("t0"), e, on="t0", by="sid", direction="backward",
                          tolerance=pd.Timedelta(hours=3))
        f = f.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    for c in ENV_FEATURES:
        if c not in f.columns:
            f[c] = np.nan
    if len(f):
        f["env_mpi_excess_kt"] = f["env_mpi_kt"] - f["wind"]
    f["env_missing"] = f["env_shear_kt"].isna().astype(float) if len(f) else []
    return f


def build_samples(tracks: pd.DataFrame, agency: str | None = "newdelhi", cfg: dict | None = None,
                  env: pd.DataFrame | None = None) -> SampleSet:
    """Build samples from a tidy track table.

    Issue times may be any observation time (RSMC New Delhi is 3-hourly); history
    and leads are exact multiples of ``timestep_h`` and looked up by timestamp, so
    off-synoptic issue times simply double the (correlated) training samples.
    The ``synoptic`` column marks 00/06/12/18 UTC issues used for verification.

    Args:
        tracks: output of :func:`tropicast.preprocessing.tracks.build_tracks`.
        agency: keep only rows from this agency (None = keep all, used for live inference).
    """
    cfg = cfg or config.load("training")
    leads = list(cfg["lead_times_h"])
    t = tracks if agency is None else tracks[tracks["agency"] == agency]
    t = t[t["wind_kt"].notna()]
    rows, seqs = [], []
    for _, g in t.groupby("sid", sort=False):
        if g["agency"].nunique() > 1:
            g = g[g["agency"] == g["agency"].mode().iat[0]]
        r, s = _storm_samples(g, cfg, leads)
        rows += r
        seqs += s
    frame = attach_env(pd.DataFrame(rows), env)
    seq = np.stack(seqs) if seqs else np.zeros((0, cfg["history_steps"], len(SEQ_FEATURES)), np.float32)
    return SampleSet(frame, seq, leads)


def split(samples: SampleSet, cfg: dict | None = None) -> dict[str, SampleSet]:
    """Season-based, event-disjoint train/val/test split."""
    cfg = cfg or config.load("training")
    out = {}
    for name, (a, b) in cfg["split"].items():
        out[name] = samples.subset(samples.frame["season"].between(a, b).values)
    assert_event_disjoint(out)
    return out


def assert_event_disjoint(parts: dict[str, SampleSet]) -> None:
    """Raise if any storm id appears in more than one split."""
    seen: dict[str, str] = {}
    for name, s in parts.items():
        for sid in s.frame["sid"].unique() if len(s.frame) else []:
            if sid in seen:
                raise AssertionError(f"Leakage: storm {sid} in both {seen[sid]} and {name}")
            seen[sid] = name
