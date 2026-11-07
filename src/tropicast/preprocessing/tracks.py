"""Build a tidy, agency-explicit track table from raw IBTrACS.

Rules:
* Each row keeps ONE agency's position/wind/pressure plus the agency name and
  wind-averaging period. RSMC New Delhi (3-min) is preferred; USA/JTWC (1-min)
  is used only when New Delhi values are absent (e.g. provisional seasons).
* No wind conversion between agencies is performed.
* Rows outside the configured bbox, with invalid coordinates, or invalid times are dropped
  and counted in the QC report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from tropicast import config

AGENCY_AVG_MIN = {"newdelhi": 3, "usa": 1}

TIDY_COLUMNS = [
    "sid", "season", "name", "subbasin", "time", "lat", "lon", "wind_kt", "pres_hpa", "agency",
    "wind_avg_min", "native_grade", "nature", "track_type", "dist2land_km", "landfall_km",
    "ci_number", "is_provisional",
]


@dataclass
class QCReport:
    input_rows: int = 0
    output_rows: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    storms: int = 0
    agency_rows: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def build_tracks(raw: pd.DataFrame, domain: dict | None = None) -> tuple[pd.DataFrame, QCReport]:
    """Convert raw IBTrACS rows to the tidy schema ``TIDY_COLUMNS``."""
    domain = domain or config.load("domain")
    qc = QCReport(input_rows=len(raw))
    df = raw.copy()

    nd_wind = _num(df["NEWDELHI_WIND"])
    usa_wind = _num(df["USA_WIND"])
    use_nd = nd_wind.notna()
    use_usa = ~use_nd & usa_wind.notna()

    out = pd.DataFrame({
        "sid": df["SID"].astype(str),
        "season": _num(df["SEASON"]).astype("Int64"),
        "name": df["NAME"].astype(object).fillna("UNNAMED").astype(str),
        "subbasin": df["SUBBASIN"].astype(object).fillna("MM").astype(str),
        "time": df["ISO_TIME"],
        "nature": df["NATURE"].astype(str),
        "track_type": df["TRACK_TYPE"].astype(str),
        "dist2land_km": _num(df["DIST2LAND"]),
        "landfall_km": _num(df["LANDFALL"]),
    })
    out["lat"] = np.where(use_nd & _num(df["NEWDELHI_LAT"]).notna(), _num(df["NEWDELHI_LAT"]),
                          np.where(use_usa & _num(df["USA_LAT"]).notna(), _num(df["USA_LAT"]), _num(df["LAT"])))
    out["lon"] = np.where(use_nd & _num(df["NEWDELHI_LON"]).notna(), _num(df["NEWDELHI_LON"]),
                          np.where(use_usa & _num(df["USA_LON"]).notna(), _num(df["USA_LON"]), _num(df["LON"])))
    out["wind_kt"] = np.where(use_nd, nd_wind, np.where(use_usa, usa_wind, np.nan))
    out["pres_hpa"] = np.where(use_nd, _num(df["NEWDELHI_PRES"]), np.where(use_usa, _num(df["USA_PRES"]), np.nan))
    out["agency"] = np.where(use_nd, "newdelhi", np.where(use_usa, "usa", "none"))
    out["wind_avg_min"] = out["agency"].map(AGENCY_AVG_MIN).astype("float")
    out["native_grade"] = np.where(use_nd, df["NEWDELHI_GRADE"].astype(object).fillna("").astype(str).str.upper(), "")
    out["ci_number"] = np.where(use_nd, _num(df["NEWDELHI_CI"]), np.nan)
    out["is_provisional"] = out["track_type"].str.contains("PROVISIONAL", case=False)

    def drop(mask: pd.Series, reason: str) -> None:
        nonlocal out
        n = int(mask.sum())
        if n:
            qc.dropped[reason] = qc.dropped.get(reason, 0) + n
        out = out[~mask]

    drop(out["time"].isna(), "invalid_time")
    drop(out["lat"].isna() | out["lon"].isna(), "missing_position")
    drop((out["lat"].abs() > 90) | (out["lon"].abs() > 180), "invalid_coordinates")
    b = domain["bbox"]
    drop(~out["lat"].between(b["lat_min"], b["lat_max"]) | ~out["lon"].between(b["lon_min"], b["lon_max"]),
         "outside_bbox")
    drop(~out["subbasin"].isin(domain["subbasins"]), "excluded_subbasin")
    drop(out["track_type"].str.contains("spur", case=False), "spur_track")
    drop(out.duplicated(["sid", "time"]), "duplicate_time")
    # physically implausible values -> set NaN, do not drop the position
    bad_w = (out["wind_kt"] < 0) | (out["wind_kt"] > 200)
    bad_p = (out["pres_hpa"] < 850) | (out["pres_hpa"] > 1030)
    qc.dropped["implausible_wind_set_nan"] = int(bad_w.sum())
    qc.dropped["implausible_pres_set_nan"] = int(bad_p.sum())
    out.loc[bad_w, "wind_kt"] = np.nan
    out.loc[bad_p, "pres_hpa"] = np.nan

    out = out.sort_values(["sid", "time"]).reset_index(drop=True)[TIDY_COLUMNS]
    qc.output_rows = len(out)
    qc.storms = int(out["sid"].nunique())
    qc.agency_rows = out["agency"].value_counts().to_dict()
    return out, qc


def to_synoptic(tracks: pd.DataFrame, hours: list[int] | None = None) -> pd.DataFrame:
    """Keep only synoptic hours (default 00/06/12/18 UTC)."""
    hours = hours or config.load("domain")["synoptic_hours"]
    return tracks[tracks["time"].dt.hour.isin(hours) & (tracks["time"].dt.minute == 0)].reset_index(drop=True)


def storm_summary(tracks: pd.DataFrame) -> pd.DataFrame:
    """One row per storm: name, period, peak wind (with agency), basin."""
    g = tracks.groupby("sid")
    s = pd.DataFrame({
        "name": g["name"].first(),
        "season": g["season"].first(),
        "subbasin": g["subbasin"].agg(lambda x: x.mode().iat[0] if len(x.mode()) else "MM"),
        "start": g["time"].min(),
        "end": g["time"].max(),
        "peak_wind_kt": g["wind_kt"].max(),
        "min_pres_hpa": g["pres_hpa"].min(),
        "agencies": g["agency"].agg(lambda x: ",".join(sorted(set(x) - {"none"}))),
        "is_provisional": g["is_provisional"].any(),
        "n_obs": g.size(),
    })
    return s.reset_index()
