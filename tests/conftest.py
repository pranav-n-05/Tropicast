"""Shared synthetic fixtures (no network, no real data needed)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tropicast.geospatial.geo import destination


def synthetic_track(sid="2000001N10085", start="2000-05-01 00:00", n=40, lat0=10.0, lon0=88.0,
                    bearing=330.0, speed_kmh=15.0, w0=25.0, dw_per_step=2.5, agency="newdelhi",
                    step_h=3, season=2000) -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq=f"{step_h}h", tz="UTC")
    d = np.arange(n) * speed_kmh * step_h
    lat, lon = destination(np.full(n, lat0), np.full(n, lon0), np.full(n, bearing), d)
    wind = np.clip(w0 + dw_per_step * np.arange(n), 0, 140)
    return pd.DataFrame({
        "sid": sid, "season": season, "name": "TEST", "subbasin": "BB", "time": times, "lat": lat, "lon": lon,
        "wind_kt": wind, "pres_hpa": 1000 - wind * 0.5, "agency": agency,
        "wind_avg_min": 3.0 if agency == "newdelhi" else 1.0, "native_grade": "", "nature": "TS",
        "track_type": "main", "dist2land_km": 300.0, "landfall_km": 300.0, "ci_number": np.nan,
        "is_provisional": False,
    })


@pytest.fixture
def straight_storm():
    return synthetic_track()


@pytest.fixture
def multi_season_tracks():
    parts = []
    for i, season in enumerate(range(1990, 2024)):
        rng = np.random.default_rng(i)
        parts.append(synthetic_track(sid=f"{season}001N10085", start=f"{season}-05-01", season=season,
                                     bearing=float(rng.uniform(300, 360)), speed_kmh=float(rng.uniform(8, 22)),
                                     dw_per_step=float(rng.uniform(-1, 3)), n=36))
    return pd.concat(parts, ignore_index=True)
