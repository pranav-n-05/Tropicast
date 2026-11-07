"""Rapid-intensification (RI) probability - EXPERIMENTAL.

Label (provisional, configs/imd_categories.yaml): RSMC New Delhi 3-min wind
increase >= ``threshold_kt`` within ``window_h`` hours of issue time. Samples
without a verifying observation at ``t0 + window_h`` are excluded (storm ended).
RI events are rare in the NIO; class imbalance is handled by reporting
proper scores (Brier, BSS vs climatology) instead of accuracy, and by NOT
re-weighting classes (re-weighting would bias probabilities).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from tropicast import config
from tropicast.datasets.samples import ALL_FEATURES, SampleSet


def ri_labels(s: SampleSet) -> tuple[np.ndarray, np.ndarray]:
    """Return (label 0/1, valid mask)."""
    ri = config.load("imd_categories")["rapid_intensification"]
    col = f"dw_{ri['window_h']}"
    dw = s.frame[col].to_numpy(float)
    valid = np.isfinite(dw)
    return (dw >= ri["threshold_kt"]).astype(int), valid


class RIModel:
    def __init__(self, kind: str = "logistic", seed: int = 42, features: list[str] | None = None):
        self.kind, self.seed = kind, seed
        self.features = features or list(ALL_FEATURES)
        self.name = f"ri_{kind}"
        self.base_rate = float("nan")
        if kind == "logistic":
            self.est = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                     LogisticRegression(C=0.5, max_iter=2000))
        else:
            self.est = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                                      min_samples_leaf=50, l2_regularization=1.0,
                                                      random_state=seed)

    def _X(self, s: SampleSet) -> np.ndarray:
        return s.frame[self.features].to_numpy(float)  # NaN handled by imputer / GBM natively

    def fit(self, train: SampleSet) -> "RIModel":
        y, v = ri_labels(train)
        self.base_rate = float(y[v].mean())
        self.est.fit(self._X(train)[v], y[v])
        return self

    def predict_proba(self, s: SampleSet) -> np.ndarray:
        return self.est.predict_proba(self._X(s))[:, 1]
