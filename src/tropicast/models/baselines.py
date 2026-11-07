"""Reference and tabular baselines.

* :class:`PersistenceModel` - linear extrapolation of the last 12 h motion; no intensity change.
  This is the no-skill reference every other model is compared against.
* :class:`RidgeModel` - CLIPER-style linear regression per lead on track/intensity features.
* :class:`GBMModel` - gradient-boosted trees; quantile loss for wind change.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from tropicast.datasets.samples import ALL_FEATURES, SampleSet
from tropicast.models.base import Prediction


class PersistenceModel:
    name = "persistence"
    features = ["mx_1", "my_1", "mx_2", "my_2", "hist_len"]

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "PersistenceModel":
        return self

    def predict(self, s: SampleSet) -> Prediction:
        f = s.frame
        two = f["hist_len"].values >= 2
        vx = np.where(two, (f["mx_1"].values + f["mx_2"].values) / 2, f["mx_1"].values)
        vy = np.where(two, (f["my_1"].values + f["my_2"].values) / 2, f["my_1"].values)
        steps = np.array(s.leads) / 6.0
        return {"dx": vx[:, None] * steps, "dy": vy[:, None] * steps,
                "dw": np.zeros((len(f), len(s.leads)))}


class _PerLead:
    """Fits one regressor per (target, lead) on rows where the target exists."""

    def __init__(self, features: list[str] | None = None):
        self.features = features or list(ALL_FEATURES)
        self.models: dict[tuple[str, int, str], object] = {}

    def _X(self, s: SampleSet) -> np.ndarray:
        return s.frame[self.features].to_numpy(dtype=float)

    def _make(self, target: str, q: str):  # pragma: no cover - abstract
        raise NotImplementedError

    def _fit_all(self, train: SampleSet, quantile_targets: dict[str, list[str]]) -> None:
        X = self._X(train)
        for kind in ("dx", "dy", "dw"):
            for L in train.leads:
                y = train.frame[f"{kind}_{L}"].to_numpy(float)
                m = np.isfinite(y)
                for q in quantile_targets.get(kind, ["mid"]):
                    est = self._make(kind, q)
                    est.fit(X[m], y[m])
                    self.models[(kind, L, q)] = est

    def _predict_all(self, s: SampleSet) -> Prediction:
        X = self._X(s)
        out: Prediction = {}
        for (kind, L, q), est in self.models.items():
            key = kind if q == "mid" else f"{kind}_{q}"
            out.setdefault(key, np.zeros((len(X), len(s.leads))))
            out[key][:, s.leads.index(L)] = est.predict(X) if len(X) else []
        return out


class RidgeModel(_PerLead):
    name = "ridge"

    def __init__(self, features: list[str] | None = None, alpha: float = 1.0):
        super().__init__(features)
        self.alpha = alpha

    def _make(self, target: str, q: str):
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=self.alpha))

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "RidgeModel":
        self._fit_all(train, {})
        return self

    def predict(self, s: SampleSet) -> Prediction:
        return self._predict_all(s)


class GBMModel(_PerLead):
    name = "gbm"

    def __init__(self, features: list[str] | None = None, quantiles=(0.05, 0.5, 0.95), seed: int = 42,
                 max_iter: int = 300):
        super().__init__(features)
        self.quantiles = quantiles
        self.seed = seed
        self.max_iter = max_iter

    def _make(self, target: str, q: str):
        common = dict(max_iter=self.max_iter, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                      l2_regularization=1.0, early_stopping=True, validation_fraction=0.15,
                      random_state=self.seed)
        if target == "dw":
            qv = {"lo": self.quantiles[0], "mid": self.quantiles[1], "hi": self.quantiles[2]}[q]
            return HistGradientBoostingRegressor(loss="quantile", quantile=qv, **common)
        return HistGradientBoostingRegressor(loss="absolute_error", **common)

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "GBMModel":
        self._fit_all(train, {"dw": ["lo", "mid", "hi"]})
        return self

    def predict(self, s: SampleSet) -> Prediction:
        p = self._predict_all(s)
        lo, hi = np.minimum(p["dw_lo"], p["dw_hi"]), np.maximum(p["dw_lo"], p["dw_hi"])
        p["dw_lo"], p["dw_hi"] = np.minimum(lo, p["dw"]), np.maximum(hi, p["dw"])
        return p


class PersistenceResidual:
    """Wrap a model so it learns the *correction* to persistence extrapolation.

    Targets become ``dx - dx_persistence`` (same for ``dy``); wind change is
    unchanged because persistence predicts zero change. This keeps short-lead
    skill near persistence while letting the model learn recurvature/slowdown.
    """

    def __init__(self, base):
        self.base = base
        self.name = f"{base.name}+pr"
        self.features = base.features
        self._pers = PersistenceModel()

    def _shift(self, s: SampleSet) -> SampleSet:
        p = self._pers.predict(s)
        f = s.frame.copy()
        for j, L in enumerate(s.leads):
            f[f"dx_{L}"] = f[f"dx_{L}"] - p["dx"][:, j]
            f[f"dy_{L}"] = f[f"dy_{L}"] - p["dy"][:, j]
        return SampleSet(f, s.seq, s.leads)

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "PersistenceResidual":
        self.base.fit(self._shift(train), self._shift(val) if val is not None else None)
        return self

    def predict(self, s: SampleSet) -> Prediction:
        out = dict(self.base.predict(s))
        p = self._pers.predict(s)
        out["dx"] = out["dx"] + p["dx"]
        out["dy"] = out["dy"] + p["dy"]
        return out
