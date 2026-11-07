"""Configuration loading. All basin/model specifics live in ``configs/*.yaml``."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(os.environ.get("TROPICAST_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = Path(os.environ.get("TROPICAST_CONFIG_DIR", PROJECT_ROOT / "configs"))
DATA_DIR = Path(os.environ.get("TROPICAST_DATA_DIR", PROJECT_ROOT / "data"))

DISCLAIMER = (
    "This platform provides experimental AI-based decision support. It is not an official "
    "weather warning, evacuation advisory, or disaster-management product. For safety-critical "
    "decisions, follow official advisories from the India Meteorological Department and relevant "
    "disaster-management authorities."
)


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    """Load ``configs/<name>.yaml`` as a dict (cached)."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh)


def artifacts_dir() -> Path:
    """Directory for trained models and registry."""
    p = PROJECT_ROOT / load("training")["artifacts_dir"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir() -> Path:
    """Directory for generated evaluation reports."""
    p = PROJECT_ROOT / load("training")["reports_dir"]
    p.mkdir(parents=True, exist_ok=True)
    return p
