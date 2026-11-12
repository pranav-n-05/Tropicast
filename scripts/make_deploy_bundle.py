"""Freeze a serving bundle (processed data + trained models + reports) into deploy/bundle/.

Hosts with small/ephemeral disks (e.g. Render free) start from this snapshot instead of
re-downloading ~2.5 GB and retraining. The bundle is a dated snapshot: the dashboard's
freshness labels show its true observation dates.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "bundle"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    reg = json.loads((ROOT / "artifacts/registry.json").read_text())
    run_dirs = {Path(reg[k]["path"]).parent for k in ("track_model", "intensity_model", "reference_model", "ri_model")}
    files = [ROOT / "artifacts/registry.json", ROOT / "artifacts/satellite_cnn.pt"]
    for d in run_dirs:
        files += sorted((ROOT / d).glob("*"))
    for name in ("tracks.pkl", "tracks_6h.pkl", "storms.pkl", "env.pkl", "dataset_manifest.json", "coast_admin1.geojson"):
        files.append(ROOT / "data/processed" / name)
    files += sorted((ROOT / "data/raw/hursat/npz").glob("*.npz"))
    for src in ("ibtracs", "ships", "hursat"):
        m = ROOT / "data/raw" / src / "manifest.json"
        if m.exists():
            files.append(m)
    files += [p for p in sorted((ROOT / "reports").glob("*")) if p.suffix in (".json", ".md")]
    total = 0
    for f in files:
        dst = OUT / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        total += f.stat().st_size
    (OUT / "BUNDLE.json").write_text(json.dumps({
        "data_version": reg["data_version"], "models_created_utc": reg["created_utc"],
        "files": len(files), "bytes": total}, indent=2))
    print(f"bundle: {len(files)} files, {total / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
