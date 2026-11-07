"""NOAA NCEI HURSAT-B1 v06 connector (public, no authentication).

HURSAT-B1: storm-centred geostationary IR (ISCCP B1) at 0.07 deg, 3-hourly,
1978-2015, keyed by IBTrACS SID (Knapp & Kossin 2007, J. Appl. Remote Sens.).
This is the open substitute for INSAT imagery until MOSDAC access is granted.

Processing per storm (keeps disk small; raw tar deleted afterwards):
* For each nominal time keep the image with the smallest view-zenith angle (VZA)
  and VZA <= ``max_vza``; record the satellite name.
* Channel: IRWIN (10.3-11.5 um window). Other channels are often missing pre-2000.
* Crop the central ``crop_px`` pixels and block-average by ``downsample``.
  Default 160 px x 0.07 deg ~ 11.2 deg box -> 80 x 80 at ~0.14 deg (~15 km).
* Missing pixels (-1 / masked) -> NaN; images with > 5 % missing are dropped.
"""
from __future__ import annotations

import json
import logging
import re
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from tropicast.ingestion.base import Connector, FetchResult, utcnow

log = logging.getLogger(__name__)
BASE = "https://www.ncei.noaa.gov/data/hurricane-satellite-hursat-b1/archive/v06"
NAME_RE = re.compile(r"(?P<sid>\d{7}[NS]\d{5})\.(?P<name>[^.]+)\.(?P<y>\d{4})\.(?P<m>\d\d)\.(?P<d>\d\d)\."
                     r"(?P<hm>\d{4})\.(?P<sss>\d+)\.(?P<sat>[^.]+)\.")


class HURSATConnector(Connector):
    source_id = "hursat"
    max_vza = 65.0
    crop_px = 160
    downsample = 2

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.json"

    @property
    def out_dir(self) -> Path:
        p = self.data_dir / "npz"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def build_index(self, sids: set[str], years: range = range(1982, 2016)) -> list[dict]:
        """List archive files whose SID is in ``sids`` (directory listings, cached)."""
        out = []
        for y in years:
            r = self._request("GET", f"{BASE}/{y}/")
            for f in re.findall(r'href="(HURSAT_b1_v06_[^"]+\.tar\.gz)"', r.text):
                sid = f.split("_")[3]
                if sid in sids:
                    out.append({"year": y, "file": f, "sid": sid, "url": f"{BASE}/{y}/{f}"})
        self.index_path.write_text(json.dumps(out, indent=1))
        return out

    def _process_tar(self, tar_path: Path, sid: str) -> dict:
        import netCDF4  # optional dependency, only needed here

        best: dict[pd.Timestamp, tuple[float, np.ndarray, str, dict]] = {}
        with tarfile.open(tar_path) as tf, tempfile.TemporaryDirectory() as td:
            for m in tf.getmembers():
                mm = NAME_RE.match(Path(m.name).name)
                if not mm or not m.isfile():
                    continue
                t = pd.Timestamp(f"{mm['y']}-{mm['m']}-{mm['d']} {mm['hm'][:2]}:{mm['hm'][2:]}", tz="UTC")
                tf.extract(m, td, filter="data")
                with netCDF4.Dataset(Path(td) / m.name) as ds:
                    vza = float(np.ma.filled(ds["VZA"][0], np.nan))
                    if not np.isfinite(vza) or vza > self.max_vza or (t in best and best[t][0] <= vza):
                        (Path(td) / m.name).unlink()
                        continue
                    ir = np.ma.filled(ds["IRWIN"][0].astype(np.float32), np.nan)
                    ir[ir <= 0] = np.nan
                    meta = {k: float(np.ma.filled(ds[k][0], np.nan)) for k in
                            ("CentLat", "CentLon", "archer_lat", "archer_lon", "eye_prob", "odt84")
                            if k in ds.variables}
                    best[t] = (vza, ir, mm["sat"], meta)
                (Path(td) / m.name).unlink()
        if not best:
            return {"sid": sid, "n": 0}
        times, imgs, sats, vzas, metas = [], [], [], [], []
        c, h, k = 150, self.crop_px // 2, self.downsample
        for t in sorted(best):
            vza, ir, sat, meta = best[t]
            crop = ir[c - h:c + h, c - h:c + h]
            if np.isnan(crop).mean() > 0.05:
                continue
            small = np.nanmean(crop.reshape(crop.shape[0] // k, k, crop.shape[1] // k, k), axis=(1, 3))
            times.append(t.value)
            imgs.append(small.astype(np.float16))
            sats.append(sat)
            vzas.append(vza)
            metas.append(meta)
        if not imgs:
            return {"sid": sid, "n": 0}
        np.savez_compressed(self.out_dir / f"{sid}.npz", time=np.array(times, dtype=np.int64),
                            ir=np.stack(imgs), sat=np.array(sats), vza=np.array(vzas, dtype=np.float32),
                            meta=json.dumps(metas))
        return {"sid": sid, "n": len(imgs), "sats": sorted(set(sats))}

    def fetch_one(self, entry: dict) -> dict:
        out = self.out_dir / f"{entry['sid']}.npz"
        if out.exists():
            return {"sid": entry["sid"], "n": -1, "status": "cached"}
        with tempfile.TemporaryDirectory() as td:
            tar = Path(td) / entry["file"]
            r = self._request("GET", entry["url"], stream=True)
            if r.status_code != 200:
                return {"sid": entry["sid"], "status": f"HTTP {r.status_code}"}
            with tar.open("wb") as fh:
                for b in r.iter_content(1 << 20):
                    fh.write(b)
            res = self._process_tar(tar, entry["sid"])
        res["status"] = "ok"
        return res

    def fetch(self, sids: set[str] | None = None, workers: int = 4) -> FetchResult:
        idx = json.loads(self.index_path.read_text()) if self.index_path.exists() else self.build_index(sids or set())
        if sids is not None:
            idx = [e for e in idx if e["sid"] in sids]
        results, errors = [], []
        with ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(self.fetch_one, e): e for e in idx}
            for f in as_completed(futs):
                try:
                    results.append(f.result())
                except Exception as exc:  # isolate per-storm failures
                    errors.append(f"{futs[f]['sid']}: {exc}")
                    log.warning("HURSAT %s failed: %s", futs[f]["sid"], exc)
        res = FetchResult(self.source_id, str(self.out_dir), BASE, utcnow().isoformat(), True,
                          status="ok" if not errors else "error", error="; ".join(errors[:10]) or None,
                          extra={"storms": len(idx), "processed": len(results), "errors": len(errors)})
        self.write_manifest(res)
        return res


def load_images(npz_dir: Path) -> pd.DataFrame:
    """Index of all processed images: sid, time, satellite, vza, file row."""
    rows = []
    for f in sorted(npz_dir.glob("*.npz")):
        z = np.load(f, allow_pickle=False)
        for i, (t, s, v) in enumerate(zip(z["time"], z["sat"], z["vza"])):
            rows.append({"sid": f.stem, "time": pd.Timestamp(int(t), tz="UTC"), "sat": str(s), "vza": float(v),
                         "row": i})
    return pd.DataFrame(rows)
