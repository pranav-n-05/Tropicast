"""End-to-end data build: raw IBTrACS -> tidy tracks -> versioned processed tables."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from tropicast import config
from tropicast.ingestion import registry
from tropicast.ingestion.base import sha256_file
from tropicast.ingestion.ibtracs import read_raw
from tropicast.preprocessing.tracks import build_tracks, storm_summary, to_synoptic

log = logging.getLogger(__name__)


def processed_dir() -> Path:
    p = config.DATA_DIR / "processed"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_raw(refresh: bool = False) -> Path:
    con = registry.get("ibtracs_ni")
    if refresh or not con.raw_path.exists() or con.read_manifest() is None:
        res = con.fetch()
        log.info("IBTrACS fetch: %s changed=%s", res.status, res.changed)
        if res.status == "error" and not con.raw_path.exists():
            raise RuntimeError(f"IBTrACS unavailable and no local copy: {res.error}")
    return con.raw_path


def build_processed(refresh: bool = False) -> dict:
    """Build tidy tables; returns the dataset manifest (with data version hash)."""
    raw_path = ensure_raw(refresh)
    raw_sha = sha256_file(raw_path)
    out = processed_dir()
    man_path = out / "dataset_manifest.json"
    cfg_hash = hashlib.sha256(json.dumps([config.load("domain"), config.load("training")], sort_keys=True,
                                         default=str).encode()).hexdigest()
    if man_path.exists():
        man = json.loads(man_path.read_text())
        if (man.get("raw_sha256"), man.get("config_sha256")) == (raw_sha, cfg_hash) and (out / "tracks.pkl").exists() and (out / "env.pkl").exists():
            return man
    tracks, qc = build_tracks(read_raw(raw_path))
    syn = to_synoptic(tracks)
    summary = storm_summary(tracks)
    env = build_env(tracks)
    env.to_pickle(out / "env.pkl")
    tracks.to_pickle(out / "tracks.pkl")
    syn.to_pickle(out / "tracks_6h.pkl")
    summary.to_pickle(out / "storms.pkl")
    version = hashlib.sha256((raw_sha + cfg_hash).encode()).hexdigest()[:12]
    man = {
        "data_version": f"ni-{version}",
        "raw_sha256": raw_sha,
        "config_sha256": cfg_hash,
        "source": config.load("sources")["sources"]["ibtracs_ni"]["url"],
        "qc": qc.as_dict(),
        "rows_6h": int(len(syn)),
        "storms": int(summary.shape[0]),
        "seasons": [int(summary["season"].min()), int(summary["season"].max())],
        "latest_observation_utc": str(tracks["time"].max()),
        "env_cases_matched": int(len(env)), "env_storms": int(env["sid"].nunique()) if len(env) else 0,
    }
    man_path.write_text(json.dumps(man, indent=2, default=str))
    (config.reports_dir() / "data_quality.json").write_text(json.dumps(man, indent=2, default=str))
    return man


def build_env(tracks: pd.DataFrame) -> pd.DataFrame:
    """SHIPS t=0 environmental predictors matched to RSMC New Delhi tracks (empty if unavailable)."""
    from tropicast.ingestion.ships import match_to_tracks, parse
    con = registry.get("ships_io")
    try:
        if not con.raw_path.exists():
            con.fetch()
        if not con.raw_path.exists():
            return pd.DataFrame(columns=["sid", "time"])
        return match_to_tracks(parse(con.raw_path), tracks[tracks["agency"] == "newdelhi"])
    except Exception as exc:  # environment is optional; never block the core build
        log.warning("SHIPS unavailable: %s", exc)
        return pd.DataFrame(columns=["sid", "time"])


def load_env() -> pd.DataFrame:
    p = processed_dir() / "env.pkl"
    return pd.read_pickle(p) if p.exists() else pd.DataFrame(columns=["sid", "time"])


def load_tracks(kind: str = "tracks_6h") -> pd.DataFrame:
    return pd.read_pickle(processed_dir() / f"{kind}.pkl")


def load_storms() -> pd.DataFrame:
    return pd.read_pickle(processed_dir() / "storms.pkl")
