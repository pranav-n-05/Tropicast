"""Track-based coastal exposure: landfall and strike probabilities (Objective 8).

Method (documented, validated on test seasons - see ``evaluate``):
1. From the calibrated track forecast take each lead's median position and 90 %
   conformal radius r90. For an isotropic bivariate normal, r_p = sigma *
   sqrt(-2 ln(1-p)), so sigma_L = r90_L / 2.146.
2. Draw N member tracks; errors are correlated between leads with an AR(1)
   coefficient rho (default 0.85) so members are smooth, then interpolate hourly.
3. Landfall = first hourly point inside a land polygon (start over water).
   Strike = member centre passes within ``strike_km`` of an admin-1 region.

Limits: centre-based only. This is NOT a wind-field, storm-surge, rainfall or
evacuation product. Boundaries: Natural Earth 1:10m admin-1 (public domain).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import STRtree
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union

from tropicast import config
from tropicast.geospatial.geo import KM_PER_NMI, destination  # noqa: F401  (KM_PER_NMI re-exported)

NE_DIR = config.DATA_DIR / "external" / "naturalearth"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"
COUNTRIES = ("IND", "BGD", "MMR", "LKA", "PAK", "OMN", "YEM", "SOM", "IRN", "ARE", "THA", "DJI", "ERI", "SAU",
             "MDV", "MYS", "IDN")
SIGMA_PER_R90 = 1 / np.sqrt(-2 * np.log(0.1))


@lru_cache(maxsize=1)
def regions() -> tuple[list[dict], STRtree, object]:
    """Admin-1 regions intersecting the domain (simplified), STRtree, and a land union."""
    cache = config.DATA_DIR / "processed" / "coast_admin1.geojson"
    if not cache.exists():
        src = NE_DIR / Path(NE_URL).name
        if not src.exists():
            import requests
            NE_DIR.mkdir(parents=True, exist_ok=True)
            src.write_bytes(requests.get(NE_URL, timeout=120).content)
        b = config.load("domain")["bbox"]
        bb = box(b["lon_min"] - 2, b["lat_min"] - 2, b["lon_max"] + 2, b["lat_max"] + 2)
        feats = []
        for f in json.loads(src.read_text())["features"]:
            p = f["properties"]
            if p.get("adm0_a3") not in COUNTRIES:
                continue
            g = shape(f["geometry"])
            if not g.intersects(bb):
                continue
            g = g.intersection(bb).simplify(0.02, preserve_topology=True)
            feats.append({"type": "Feature", "geometry": g.__geo_interface__,
                          "properties": {"name": p.get("name"), "country": p.get("admin"), "adm0": p.get("adm0_a3")}})
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    fc = json.loads(cache.read_text())["features"]
    geoms = [shape(f["geometry"]) for f in fc]
    return [f["properties"] for f in fc], STRtree(geoms), unary_union(geoms)


def _members(lat0, lon0, lats, lons, r90, leads, n, rho, rng):
    sig = np.asarray(r90) * SIGMA_PER_R90
    z = np.zeros((n, len(leads), 2))
    z[:, 0] = rng.standard_normal((n, 2))
    for j in range(1, len(leads)):
        z[:, j] = rho * z[:, j - 1] + np.sqrt(1 - rho ** 2) * rng.standard_normal((n, 2))
    dist = np.hypot(z[..., 0], z[..., 1]) * sig[None, :]
    brg = np.degrees(np.arctan2(z[..., 0], z[..., 1]))
    mlat, mlon = destination(np.broadcast_to(lats, dist.shape), np.broadcast_to(lons, dist.shape), brg, dist)
    t = np.r_[0, leads]
    hours = np.arange(0, leads[-1] + 1)
    full_lat = np.concatenate([np.full((n, 1), lat0), mlat], 1)
    full_lon = np.concatenate([np.full((n, 1), lon0), mlon], 1)
    hl = np.stack([np.interp(hours, t, r) for r in full_lat])
    ho = np.stack([np.interp(hours, t, r) for r in full_lon])
    return hours, hl, ho


def exposure(fc: dict, n: int = 500, rho: float = 0.85, strike_km: float = 100.0, seed: int = 0) -> dict:
    """Landfall / strike probabilities for one forecast payload (from inference.forecast)."""
    props, tree, land = regions()
    leads = [L["lead_h"] for L in fc["leads"]]
    rng = np.random.default_rng(seed)
    hours, hl, ho = _members(fc["initial"]["lat"], fc["initial"]["lon"],
                             np.array([L["lat"] for L in fc["leads"]]), np.array([L["lon"] for L in fc["leads"]]),
                             [L["track_radius_km_90"] for L in fc["leads"]], leads, n, rho, rng)
    start_on_land = land.contains(Point(fc["initial"]["lon"], fc["initial"]["lat"]))
    land_region, land_hour = [], []
    strike_counts = np.zeros(len(props))
    for i in range(n):
        pts = [Point(x, y) for x, y in zip(ho[i], hl[i])]
        lf_r, lf_h = None, None
        if not start_on_land:
            for h, pt in zip(hours, pts):
                hit = tree.query(pt, predicate="intersects")
                if len(hit):
                    lf_r, lf_h = int(hit[0]), int(h)
                    break
        land_region.append(lf_r)
        land_hour.append(lf_h)
        deg = strike_km / 111.0
        near = set()
        for pt in pts[::3]:
            for k in tree.query(pt.buffer(deg / max(np.cos(np.radians(pt.y)), 0.3))):
                near.add(int(k))
        for k in near:
            strike_counts[k] += 1
    lr = pd.Series([r for r in land_region if r is not None], dtype="float")
    by_region = (lr.value_counts() / n).head(8)
    lh = [h for h in land_hour if h is not None]
    top_strike = np.argsort(-strike_counts)[:10]
    return {
        "product": "EXPERIMENTAL_TRACK_EXPOSURE",
        "members": n, "ar1_rho": rho, "strike_radius_km": strike_km,
        "starts_over_land": bool(start_on_land),
        "p_landfall_72h": None if start_on_land else round(float(np.mean([r is not None for r in land_region])), 3),
        "landfall_regions": [{"region": props[int(k)]["name"], "country": props[int(k)]["country"],
                              "probability": round(float(v), 3)} for k, v in by_region.items()],
        "landfall_time_h": ({"p10": int(np.percentile(lh, 10)), "median": int(np.median(lh)),
                             "p90": int(np.percentile(lh, 90))} if lh else None),
        "strike_probability": [{"region": props[int(k)]["name"], "country": props[int(k)]["country"],
                                "probability": round(float(strike_counts[k] / n), 3)}
                               for k in top_strike if strike_counts[k] > 0],
        "limitations": "Centre-track probabilities only; not wind, surge, rainfall or evacuation guidance.",
    }


def observed_landfall(track: pd.DataFrame, t0: pd.Timestamp, hours: int = 72) -> bool | None:
    """True if the observed centre goes from water at t0 to land (DIST2LAND == 0) within ``hours``."""
    g = track.set_index("time").sort_index()
    if t0 not in g.index or g.loc[t0, "dist2land_km"] <= 0:
        return None
    fut = g[(g.index > t0) & (g.index <= t0 + pd.Timedelta(hours=hours))]
    if fut.empty or fut.index.max() < t0 + pd.Timedelta(hours=min(hours, 24)):
        return None
    return bool((fut["dist2land_km"] <= 0).any())
