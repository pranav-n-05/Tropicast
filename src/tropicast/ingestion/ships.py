"""SHIPS developmental database, North Indian Ocean (CIRA/RAMMB, public).

File: lsdiagi_1990_2021_5day.txt (cases every 6 h along JTWC best tracks).
Predictors are computed from NCEP global analyses around the storm centre;
see ships_predictor_file_2026.pdf (DeMaria & Kaplan 1994 lineage).

LEAKAGE RULE: in the developmental file, columns for t > 0 are evaluated along
the *verifying* best track (perfect-prognosis). We only ever read the t = 0
column (and t <= 0 history), which is what an operational analysis provides.

Cases are matched to IBTrACS storms by time + nearest RSMC New Delhi position
(<= 150 km), so environmental features attach to our IMD-labelled samples.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tropicast.geospatial.geo import haversine_km
from tropicast.ingestion.base import Connector, FetchResult

URL = "https://rammb-data.cira.colostate.edu/ships/data/IO/lsdiagi_1990_2021_5day.txt"
DOC_URL = "https://rammb-data.cira.colostate.edu/ships/data/ships_predictor_file_2026.pdf"
T0_COL = 2  # columns are -12, -6, 0, 6, ...

# label -> (output name, scale divisor). Units after scaling in comments.
PREDICTORS = {
    "SHRD": ("env_shear_kt", 10),        # 850-200 hPa shear, 200-800 km
    "SHDC": ("env_shear_core_kt", 10),   # same, vortex removed, 0-500 km
    "SHTD": ("env_shear_heading", 1),    # deg (westerly = 90)
    "RHLO": ("env_rh_850_700", 1),       # %
    "RHMD": ("env_rh_700_500", 1),       # %
    "RHHI": ("env_rh_500_300", 1),       # %
    "RSST": ("env_sst_c", 10),           # deg C (Reynolds)
    "CSST": ("env_sst_clim_c", 10),      # deg C climatological
    "COHC": ("env_ohc_clim", 1),         # kJ/cm2 climatological OHC
    "VMPI": ("env_mpi_kt", 1),           # Bister-Emanuel MPI
    "D200": ("env_div200", 1),           # s-1 * 1e7
    "Z850": ("env_vort850", 1),          # s-1 * 1e7
    "U200": ("env_u200_kt", 10),         # 200 hPa zonal wind (kt), 200-800 km
    "EPOS": ("env_thetae_excess", 10),   # deg C
    "TWAC": ("env_tangwind850", 10),     # m/s, 0-600 km symmetric tangential wind
}
ENV_FEATURES = [v[0] for v in PREDICTORS.values()] + ["env_mpi_excess_kt", "env_shear_u", "env_shear_v"]


class SHIPSConnector(Connector):
    source_id = "ships"

    @property
    def raw_path(self) -> Path:
        return self.data_dir / Path(URL).name

    def fetch(self) -> FetchResult:
        res = self.download(URL, self.raw_path)
        doc = self.data_dir / Path(DOC_URL).name
        if not doc.exists():
            try:
                self.download(DOC_URL, doc)
            except Exception:  # documentation is optional
                pass
        return res


def parse(path: Path) -> pd.DataFrame:
    """Parse lsdiag text into one row per case with t=0 predictors."""
    rows, cur = [], None
    with path.open() as fh:
        for line in fh:
            label = line[115:].split()[0] if len(line) > 115 and line[115:].split() else ""
            if label == "HEAD":
                p = line.split()
                yy, mmdd, hh = p[1][:2], p[1][2:], int(p[2])
                year = (1900 if int(yy) > 50 else 2000) + int(yy)
                cur = {"atcf": p[-2] if len(p) >= 8 else p[0],
                       "time": pd.Timestamp(f"{year}-{mmdd[:2]}-{mmdd[2:]} {hh:02d}:00", tz="UTC"),
                       "ships_vmax": float(p[3]), "ships_lat": float(p[4]), "ships_lon": float(p[5])}
                rows.append(cur)
            elif label == "TYPE" and cur is not None:
                v = line[T0_COL * 5:(T0_COL + 1) * 5].strip()
                cur["ships_type"] = int(v) if v and v != "9999" else np.nan
            elif cur is not None and label in PREDICTORS:
                v = line[T0_COL * 5:(T0_COL + 1) * 5].strip()
                name, scale = PREDICTORS[label]
                cur[name] = float(v) / scale if v and v not in ("9999", "-9999") else np.nan
    df = pd.DataFrame(rows)
    for name, _ in PREDICTORS.values():
        if name not in df.columns:
            df[name] = np.nan
    df["ships_lon"] = np.where(df["ships_lon"] < 0, df["ships_lon"] + 360, df["ships_lon"])
    df.loc[df["ships_lon"] > 180, "ships_lon"] -= 360
    df["env_mpi_excess_kt"] = df["env_mpi_kt"] - df["ships_vmax"]
    hd = np.radians(df["env_shear_heading"])  # heading the shear vector points to
    df["env_shear_u"] = df["env_shear_kt"] * np.sin(hd)
    df["env_shear_v"] = df["env_shear_kt"] * np.cos(hd)
    return df


def match_to_tracks(ships: pd.DataFrame, tracks: pd.DataFrame, max_km: float = 150.0) -> pd.DataFrame:
    """Attach IBTrACS ``sid`` to SHIPS cases by exact time and nearest position."""
    t = tracks[["sid", "time", "lat", "lon"]]
    m = ships.merge(t, on="time", how="inner")
    m["dist_km"] = haversine_km(m["ships_lat"], m["ships_lon"], m["lat"], m["lon"])
    m = m[m["dist_km"] <= max_km].sort_values("dist_km").drop_duplicates(["time", "atcf"])
    m = m.drop_duplicates(["sid", "time"])
    return m.drop(columns=["lat", "lon"]).reset_index(drop=True)
