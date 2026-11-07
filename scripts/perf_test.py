"""API latency benchmark (in-process, TestClient). Writes reports/performance.json.

Usage: python scripts/perf_test.py [--n 30]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time

from fastapi.testclient import TestClient

os.environ.setdefault("TROPICAST_DB", os.path.join(tempfile.mkdtemp(), "perf.sqlite"))
from tropicast import config  # noqa: E402
from tropicast.api.app import RATE_LIMIT, _hits, app  # noqa: E402

AMPHAN = "2020136N10088"
CASES = {
    "health": "/api/v1/health",
    "storm_list": "/api/v1/storms?season_from=1990&min_wind=34",
    "storm_track": f"/api/v1/storms/{AMPHAN}",
    "forecast_hindcast": f"/api/v1/storms/{AMPHAN}/forecast?issue_time=2020-05-18T12:00:00Z",
    "exposure_300_members": f"/api/v1/storms/{AMPHAN}/exposure?issue_time=2020-05-18T12:00:00Z&members=300",
    "satellite_gradcam": "/api/v1/storms/2007151N14072/satellite",
    "active": "/api/v1/active",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    c = TestClient(app)
    out = {}
    for name, url in CASES.items():
        n = a.n if "exposure" not in name and "satellite" not in name else max(5, a.n // 5)
        _hits.clear()  # benchmark latency, not the limiter
        c.get(url)  # warm-up (model/cache load)
        ts, codes = [], []
        for _ in range(n):
            t = time.perf_counter()
            r = c.get(url)
            ts.append((time.perf_counter() - t) * 1000)
            codes.append(r.status_code)
        ts.sort()
        out[name] = {"n": n, "status": sorted(set(codes)), "p50_ms": round(statistics.median(ts), 1),
                     "p95_ms": round(ts[int(0.95 * (len(ts) - 1))], 1), "max_ms": round(ts[-1], 1)}
        print(name, out[name])
    out["_meta"] = {"rate_limit_per_min": RATE_LIMIT, "note": "single process, CPU, warm cache; limiter reset between cases"}
    (config.reports_dir() / "performance.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
