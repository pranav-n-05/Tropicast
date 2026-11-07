"""Common forecaster interface.

``predict`` returns a dict of arrays with shape ``(n_samples, n_leads)``:

* ``dx``, ``dy``  : median east/north displacement (km)
* ``dw``          : median wind change (kt)
* optional ``dw_lo``, ``dw_hi`` : raw lower/upper wind-change quantiles
* optional ``track_sigma`` : per-sample track spread scale (km) for normalised conformal
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

from tropicast.datasets.samples import SampleSet

Prediction = dict[str, np.ndarray]


class Forecaster(Protocol):
    name: str
    features: list[str]

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "Forecaster": ...

    def predict(self, s: SampleSet) -> Prediction: ...
