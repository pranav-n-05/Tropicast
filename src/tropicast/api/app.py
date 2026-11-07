"""FastAPI service: historical tracks, experimental forecasts, source status, evaluation.

All forecast responses are labelled ``EXPERIMENTAL_AI_FORECAST`` and include the
disclaimer. Versioned under ``/api/v1``. Static dashboard served at ``/``.
"""
from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict, deque
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from tropicast import __version__, config
from tropicast.classification import imd
from tropicast.database import store
from tropicast.datasets import build
from tropicast.inference import forecast as fc_mod
from tropicast.ingestion.registry import all_connectors
from tropicast.realtime import pipeline

log = logging.getLogger("tropicast.api")
app = FastAPI(title="Tropicast - NIO cyclone intelligence (experimental)", version=__version__,
              description=config.DISCLAIMER)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

# ---- simple per-IP rate limit (sliding window) -----------------------------
RATE_LIMIT = 120  # requests per minute
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "?"
        q = _hits[ip]
        now = time.monotonic()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        q.append(now)
    return await call_next(request)


# ---- helpers ---------------------------------------------------------------
_cache: dict[str, Any] = {}


def _tracks() -> pd.DataFrame:
    man_path = build.processed_dir() / "dataset_manifest.json"
    if not man_path.exists():
        raise HTTPException(503, "Data not built. Run `tropicast ingest`.")
    key = man_path.stat().st_mtime
    if _cache.get("key") != key:
        _cache.update(key=key, tracks=build.load_tracks("tracks"), storms=build.load_storms(), env=build.load_env(),
                      manifest=json.loads(man_path.read_text()))
    return _cache["tracks"]


def _clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def _envelope(data: Any, **meta) -> dict:
    return {"disclaimer": config.DISCLAIMER, "data_version": _cache.get("manifest", {}).get("data_version"),
            **meta, "data": data}


# ---- endpoints ---------------------------------------------------------------
@app.get("/api/v1/health")
def health() -> dict:
    ok_data = (build.processed_dir() / "dataset_manifest.json").exists()
    ok_models = (config.artifacts_dir() / "registry.json").exists()
    return {"status": "ok" if ok_data and ok_models else "degraded", "version": __version__,
            "data_built": ok_data, "models_trained": ok_models}


@app.get("/api/v1/sources")
def sources() -> dict:
    out = {k: c.status() for k, c in all_connectors().items()}
    for k, v in out.items():
        v.update({kk: vv for kk, vv in config.load("sources")["sources"][k].items()
                  if kk in ("auth", "notes", "status")})
    return _envelope(out)


@app.get("/api/v1/storms")
def storms(season_from: int = 1982, season_to: int = 2100, q: str | None = None,
           min_wind: float = 0, limit: int = Query(500, le=3000)) -> dict:
    _tracks()
    s = _cache["storms"]
    s = s[s["season"].between(season_from, season_to) & (s["peak_wind_kt"].fillna(0) >= min_wind)]
    if q:
        s = s[s["name"].str.contains(q, case=False, na=False) | s["sid"].str.contains(q, case=False)]
    s = s.sort_values("start", ascending=False).head(limit).copy()
    t = _cache["tracks"]
    nd_peak = t[t["agency"] == "newdelhi"].groupby("sid")["wind_kt"].max()
    s["peak_wind_imd_kt"] = s["sid"].map(nd_peak)
    s["peak_category"] = [imd.classify(w).code if pd.notna(w) else None for w in s["peak_wind_imd_kt"]]
    return _envelope(_records(s), product="HISTORICAL_BEST_TRACK", count=len(s))


@app.get("/api/v1/storms/{sid}")
def storm(sid: str) -> dict:
    t = _tracks()
    g = t[t["sid"] == sid]
    if g.empty:
        raise HTTPException(404, f"Unknown storm {sid}")
    g = g.copy()
    g["category"] = [imd.classify(w).code if a == "newdelhi" and pd.notna(w) else None
                     for w, a in zip(g["wind_kt"], g["agency"])]
    last = g["time"].max()
    product = "PROVISIONAL_TRACK" if g["is_provisional"].any() else "HISTORICAL_BEST_TRACK"
    return _envelope(_records(g), product=product, sid=sid, name=g["name"].iat[0],
                     freshness=pipeline.freshness(last))


@app.get("/api/v1/storms/{sid}/forecast")
def storm_forecast(sid: str, issue_time: str | None = None) -> dict:
    t0 = time.time()
    t = _tracks()
    g = t[t["sid"] == sid]
    if g.empty:
        raise HTTPException(404, f"Unknown storm {sid}")
    try:
        fc = fc_mod.forecast_storm(g, pd.Timestamp(issue_time) if issue_time else None, env=_cache.get("env"))
    except fc_mod.ModelsNotTrainedError as exc:
        store.audit("forecast", sid, issue_time, None, None, (time.time() - t0) * 1e3, "error", str(exc))
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        store.audit("forecast", sid, issue_time, None, None, (time.time() - t0) * 1e3, "error", str(exc))
        raise HTTPException(422, str(exc))
    # attach verifying observations when this is a hindcast
    obs = g.set_index("time")
    verif = []
    for e in fc["leads"]:
        vt = pd.Timestamp(e["valid_time"])
        if vt in obs.index:
            r = obs.loc[vt]
            verif.append({"lead_h": e["lead_h"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                          "wind_kt": _clean(float(r["wind_kt"])) if pd.notna(r["wind_kt"]) else None})
    fc["verification"] = verif
    fc["mode"] = "hindcast" if verif else "forecast"
    fc["freshness"] = pipeline.freshness(g["time"].max())
    store.audit("forecast", sid, fc["issue_time"], fc["model"]["track"], fc["model"]["data_version"],
                (time.time() - t0) * 1e3, "ok")
    return fc


@app.get("/api/v1/storms/{sid}/satellite")
def storm_satellite(sid: str, time: str | None = None) -> dict:
    from tropicast.satellite import inference as sat
    t = _tracks()
    g = t[t["sid"] == sid]
    if g.empty:
        raise HTTPException(404, f"Unknown storm {sid}")
    try:
        prod = sat.product(sid, time)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc))
    row = g[g["time"] == pd.Timestamp(prod["time"])]
    if len(row) and pd.notna(row["wind_kt"].iat[0]):
        prod["best_track_wind_kt"] = float(row["wind_kt"].iat[0])
        prod["best_track_agency"] = row["agency"].iat[0]
    return prod


@app.get("/api/v1/storms/{sid}/exposure")
def storm_exposure(sid: str, issue_time: str | None = None, members: int = Query(300, ge=50, le=1000)) -> dict:
    from tropicast.risk.landfall import exposure
    fc = storm_forecast(sid, issue_time)
    ex = exposure(fc, n=members)
    ex.update({"disclaimer": config.DISCLAIMER, "sid": sid, "issue_time": fc["issue_time"],
               "model": fc["model"], "mode": fc["mode"]})
    return ex


@app.get("/api/v1/evaluation/{name}")
def evaluation_extra(name: str) -> dict:
    files = {"satellite": "satellite_evaluation.json", "landfall": "landfall_evaluation.json",
             "localization": "localization.json", "data_quality": "data_quality.json"}
    if name not in files:
        raise HTTPException(404, f"Unknown report {name}")
    p = config.reports_dir() / files[name]
    if not p.exists():
        raise HTTPException(503, f"Not yet evaluated: {name}")
    return json.loads(p.read_text())


@app.get("/api/v1/active")
def active() -> dict:
    t = _tracks()
    act = pipeline.active_storms(t)
    stored = {f["sid"]: f for f in store.latest_forecasts()}
    out = []
    for _, r in act.iterrows():
        out.append({"sid": r["sid"], "name": t.loc[t["sid"] == r["sid"], "name"].iat[0],
                    "freshness": pipeline.freshness(r["last_obs"]), "forecast": stored.get(r["sid"])})
    return _envelope(out, product="ACTIVE_SYSTEMS", note=(
        "Active = latest observation within 72 h of the newest IBTrACS record. IBTrACS provisional data lags "
        "real time; check freshness.status before use."))


@app.get("/api/v1/models")
def models() -> dict:
    p = config.artifacts_dir() / "registry.json"
    if not p.exists():
        raise HTTPException(503, "No trained models. Run `tropicast train`.")
    return json.loads(p.read_text())


@app.get("/api/v1/evaluation")
def evaluation() -> dict:
    p = config.reports_dir() / "evaluation.json"
    if not p.exists():
        raise HTTPException(503, "Not yet evaluated. Run `tropicast train`.")
    return json.loads(p.read_text())


@app.get("/api/v1/pipeline/runs")
def runs(limit: int = Query(20, le=200)) -> list[dict]:
    return store.recent_runs(limit)


@app.post("/api/v1/pipeline/run", status_code=202)
def trigger(bg: BackgroundTasks) -> dict:
    bg.add_task(pipeline.run_once)
    return {"status": "scheduled"}


@app.get("/api/v1/notifications")
def notifications(limit: int = Query(50, le=500)) -> list[dict]:
    return store.notifications(limit)


@app.get("/api/v1/audit")
def audit(limit: int = Query(100, le=1000)) -> list[dict]:
    return store.audit_tail(limit)


@app.get("/api/v1/config/categories")
def categories() -> dict:
    return config.load("imd_categories")


_front = config.PROJECT_ROOT / "frontend"
if _front.exists():
    app.mount("/", StaticFiles(directory=_front, html=True), name="dashboard")
