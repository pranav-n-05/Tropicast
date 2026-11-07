"""IMD intensity classification from maximum sustained wind.

Thresholds come from ``configs/imd_categories.yaml``. The input wind must be an
RSMC New Delhi (3-minute mean) value; other agencies' winds are refused rather
than silently converted.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tropicast import config


class AgencyMismatchError(ValueError):
    """Raised when wind from a different averaging convention is classified."""


@dataclass(frozen=True)
class Category:
    code: str
    name: str
    min_kt: float
    max_kt: float | None


def categories() -> list[Category]:
    cfg = config.load("imd_categories")
    return [Category(c["code"], c["name"], c["min_kt"], c["max_kt"]) for c in cfg["categories"]]


def classify(wind_kt: float | None, agency: str = "newdelhi") -> Category:
    """Return the IMD category for ``wind_kt``.

    Raises:
        AgencyMismatchError: if ``agency`` is not the configured classification agency.
    """
    cfg = config.load("imd_categories")
    if agency != cfg["agency"]:
        raise AgencyMismatchError(
            f"IMD classes are defined on {cfg['agency']} {cfg['wind_averaging_minutes']}-min winds; "
            f"got agency={agency!r}. No conversion is applied."
        )
    low = cfg["below_threshold"]
    if wind_kt is None or (isinstance(wind_kt, float) and np.isnan(wind_kt)):
        return Category("UNK", "Unknown", float("nan"), None)
    for c in reversed(categories()):  # highest class whose lower bound is met
        if wind_kt >= c.min_kt:
            return c
    return Category(low["code"], low["name"], 0, categories()[0].min_kt - 1)


def category_probabilities(quantile_winds: dict[float, float]) -> dict[str, float]:
    """Approximate category probabilities from wind quantiles (piecewise-linear CDF)."""
    qs = np.array(sorted(quantile_winds))
    vs = np.array([quantile_winds[q] for q in qs])
    vs = np.maximum.accumulate(vs)  # enforce monotone quantiles

    def cdf(x: float) -> float:
        if x <= vs[0]:
            return float(qs[0] * np.exp(-(vs[0] - x) / 5.0))
        if x >= vs[-1]:
            return float(1 - (1 - qs[-1]) * np.exp(-(x - vs[-1]) / 5.0))
        return float(np.interp(x, vs, qs))

    out: dict[str, float] = {}
    cats = categories()
    out["LOW"] = cdf(cats[0].min_kt)
    for c in cats:
        upper = 1.0 if c.max_kt is None else cdf(c.max_kt + 1)
        out[c.code] = max(0.0, upper - cdf(c.min_kt))
    total = sum(out.values())
    return {k: v / total for k, v in out.items()}
