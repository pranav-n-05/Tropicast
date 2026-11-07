"""Real-time(-capable) pipeline.

Each cycle: check every source -> fetch IBTrACS if changed -> rebuild tables ->
find *active* storms (last observation within ``active_window_h`` of now) ->
issue forecasts -> store -> record timings/errors. A failing source or storm
never aborts the cycle; failures are recorded.

Freshness honesty: IBTrACS provisional data lags real time by days. A storm is
labelled ``real_time`` only if its last observation is within the source's
``expected_latency_hours``; otherwise ``recent`` or ``stale``. Without a
low-latency feed (MOSDAC/JTWC/IMD bulletins) this pipeline is NOT real-time.
"""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone

import pandas as pd

from tropicast import config
from tropicast.database import store
from tropicast.datasets import build
from tropicast.inference import forecast as fc_mod
from tropicast.ingestion.registry import all_connectors

log = logging.getLogger(__name__)
ACTIVE_WINDOW_H = 72


def freshness(last_obs: pd.Timestamp, now: datetime | None = None) -> dict:
    src = config.load("sources")["sources"]["ibtracs_ni"]
    now = now or datetime.now(timezone.utc)
    age_h = (pd.Timestamp(now) - last_obs).total_seconds() / 3600
    if age_h <= 6:
        status = "real_time"
    elif age_h <= src["expected_latency_hours"]:
        status = "recent"
    elif age_h <= src["stale_after_hours"]:
        status = "delayed"
    elif age_h <= 24 * 30:
        status = "stale"
    else:
        status = "archive"  # historical record, not a live system
    return {"last_observation_utc": last_obs.isoformat(), "age_hours": round(age_h, 1), "status": status}


def active_storms(tracks: pd.DataFrame, now: datetime | None = None,
                  window_h: float = ACTIVE_WINDOW_H) -> pd.DataFrame:
    """Storms whose latest observation is within ``window_h`` of the latest data time and of now.

    Two references are used so a stale file never makes old storms look active.
    """
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    last = tracks.groupby("sid")["time"].max()
    src = config.load("sources")["sources"]["ibtracs_ni"]
    horizon = pd.Timedelta(hours=window_h + src["stale_after_hours"])
    keep = last[(last >= tracks["time"].max() - pd.Timedelta(hours=window_h)) & (last >= now - horizon)]
    return keep.rename("last_obs").reset_index()


def _emit(kind: str, message: str, sid: str | None, key: str) -> None:
    """Record a notification once; optionally POST it to TROPICAST_WEBHOOK_URL (operator-configured)."""
    import os

    if not store.notify(kind, message, sid, key):
        return
    url = os.environ.get("TROPICAST_WEBHOOK_URL")
    if url:
        try:
            import requests
            requests.post(url, json={"kind": kind, "sid": sid, "message": message,
                                     "disclaimer": config.DISCLAIMER}, timeout=10)
        except Exception as exc:  # notification failure must not break the cycle
            log.warning("webhook failed: %s", exc)


def run_once(now: datetime | None = None) -> dict:
    started = store.now()
    t0 = time.time()
    details: dict = {"sources": {}, "storms": [], "errors": []}
    for key, con in all_connectors().items():
        try:
            res = con.fetch() if key == "ibtracs_ni" else None
            details["sources"][key] = {"fetch": res.status if res else "skipped", **con.status()}
        except Exception as exc:  # isolate failures
            details["sources"][key] = {"fetch": "error", "error": str(exc)}
            details["errors"].append(f"{key}: {exc}")
    for key, info in details["sources"].items():
        if info.get("fetch") == "error":
            _emit("source_error", f"Source {key} failed: {info.get('error', 'see manifest')}", None,
                  f"srcerr:{key}:{store.now()[:13]}")
    try:
        man = build.build_processed()
        details["data_version"] = man["data_version"]
        tracks = build.load_tracks("tracks")
        act = active_storms(tracks, now)
        fc_mod.reset_cache()
        for _, row in act.iterrows():
            g = tracks[tracks["sid"] == row["sid"]]
            entry = {"sid": row["sid"], "name": g["name"].iat[0], **freshness(row["last_obs"], now)}
            try:
                fc = fc_mod.forecast_storm(g, env=build.load_env())
                fc["freshness"] = {k: entry[k] for k in ("last_observation_utc", "age_hours", "status")}
                store.save_forecast(fc, source="ibtracs_ni")
                entry["forecast"] = "issued"
                _emit("new_system", f"Active system {entry['name']} ({row['sid']}) detected; last obs "
                      f"{entry['last_observation_utc']} ({entry['status']}).", row["sid"], f"new:{row['sid']}")
                cat = fc["initial"]["category"]
                if cat:
                    _emit("category", f"{entry['name']} classified {cat} at {fc['issue_time']} (IMD scale, "
                          "best-track input).", row["sid"], f"cat:{row['sid']}:{cat}")
            except Exception as exc:
                entry["forecast"] = f"failed: {exc}"
                details["errors"].append(f"{row['sid']}: {exc}")
            details["storms"].append(entry)
    except Exception as exc:
        details["errors"].append(f"pipeline: {exc}")
        log.error(traceback.format_exc())
    dur = time.time() - t0
    status = "ok" if not details["errors"] else "partial"
    store.record_run(started, dur, status, details)
    details.update({"status": status, "duration_s": round(dur, 2)})
    return details


def loop(interval_min: float = 60.0) -> None:  # pragma: no cover - long running
    while True:
        try:
            d = run_once()
            log.info("cycle %s in %.1fs: %d active storms", d["status"], d["duration_s"], len(d["storms"]))
        except Exception:
            log.error("cycle crashed:\n%s", traceback.format_exc())
        time.sleep(interval_min * 60)
