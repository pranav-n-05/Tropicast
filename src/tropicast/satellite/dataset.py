"""Satellite sample table: HURSAT-B1 IR images joined to RSMC New Delhi labels.

One row per (storm, 3-hourly time) with an IR image whose view-zenith angle is
<= 65 deg. Labels: IMD 3-min wind at the image time (estimation target) and
wind change to +24 h (forecast target). Auxiliary inputs (track history,
environment) come from the main sample builder so every modality is aligned on
(sid, t0). Images at t-6 h and t-12 h are attached when available (temporal IR).

CV folds are contiguous season blocks (event- and season-disjoint).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from tropicast import config
from tropicast.datasets import build
from tropicast.datasets.samples import build_samples
from tropicast.ingestion.hursat import load_images

FOLDS = [(1982, 1995), (1996, 2001), (2002, 2006), (2007, 2011), (2012, 2015)]
BT_MEAN, BT_STD = 250.0, 30.0


def npz_dir() -> Path:
    return config.DATA_DIR / "raw" / "hursat" / "npz"


@dataclass
class SatSet:
    frame: pd.DataFrame
    images: np.ndarray          # (n, 80, 80) float32 brightness temperature, K (NaN filled)
    prev6: np.ndarray           # (n, 80, 80) image at t-6 h (NaN where missing)
    prev12: np.ndarray

    def subset(self, m) -> "SatSet":
        m = np.asarray(m)
        return SatSet(self.frame[m].reset_index(drop=True), self.images[m], self.prev6[m], self.prev12[m])


def _fill(img: np.ndarray) -> np.ndarray:
    img = img.astype(np.float32)
    if np.isnan(img).any():
        img[np.isnan(img)] = np.nanmedian(img)
    return img


def build_satset() -> SatSet:
    """Assemble images + aligned labels/features (cached in data/processed/satset.npz)."""
    cache = build.processed_dir() / "satset.npz"
    cache_meta = build.processed_dir() / "satset.pkl"
    if cache.exists() and cache_meta.exists():
        z = np.load(cache)
        return SatSet(pd.read_pickle(cache_meta), z["images"], z["prev6"], z["prev12"])
    idx = load_images(npz_dir())
    tracks = build.load_tracks("tracks")
    cfg = {**config.load("training"), "min_wind_kt": 0}
    samples = build_samples(tracks, agency="newdelhi", cfg=cfg, env=build.load_env()).frame
    samples = samples.rename(columns={"t0": "time"})
    m = idx.merge(samples, on=["sid", "time"], how="inner")
    m = m[m["season"].between(FOLDS[0][0], FOLDS[-1][1])].reset_index(drop=True)
    cache_imgs: dict[str, np.lib.npyio.NpzFile] = {}

    def get(sid: str, row: int) -> np.ndarray:
        if sid not in cache_imgs:
            cache_imgs[sid] = np.load(npz_dir() / f"{sid}.npz")
        return _fill(cache_imgs[sid]["ir"][row])

    by_key = {(r.sid, r.time): r.row for r in idx.itertuples()}
    imgs, p6, p12 = [], [], []
    nan_img = np.full((80, 80), np.nan, np.float32)
    for r in m.itertuples():
        imgs.append(get(r.sid, r.row))
        for lag, store in ((6, p6), (12, p12)):
            k = (r.sid, r.time - pd.Timedelta(hours=lag))
            store.append(get(r.sid, by_key[k]) if k in by_key else nan_img)
    m["fold"] = np.select([m["season"].between(a, b) for a, b in FOLDS], list(range(len(FOLDS))), -1)
    m["has_prev6"] = [k is not None for k in [(1 if not np.isnan(x).all() else None) for x in p6]]
    s = SatSet(m, np.stack(imgs), np.stack(p6), np.stack(p12))
    np.savez_compressed(cache, images=s.images, prev6=s.prev6, prev12=s.prev12)
    m.to_pickle(cache_meta)
    return s


def normalise(bt: np.ndarray) -> np.ndarray:
    return (bt - BT_MEAN) / BT_STD
