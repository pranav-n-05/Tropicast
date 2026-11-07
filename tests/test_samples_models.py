import numpy as np
import pandas as pd
import pytest

from tropicast import config
from tropicast.datasets.samples import assert_event_disjoint, build_samples, split
from tropicast.models.baselines import GBMModel, PersistenceModel, PersistenceResidual, RidgeModel
from tropicast.models.uncertainty import ConformalCalibrator, _conf_q, track_errors_km


def test_targets_and_persistence_exact_on_straight_track(straight_storm):
    s = build_samples(straight_storm)
    full = s.subset((s.frame["hist_len"] == 4).values)
    assert len(full.frame) > 0
    err = track_errors_km(full, PersistenceModel().predict(full))
    dist = np.array(full.leads) * 15.0  # km travelled at 15 km/h
    # constant great-circle motion -> persistence exact up to local-plane curvature (< 2 % of distance)
    assert np.nanmax(err / dist) < 0.02
    # wind change target: +2.5 kt per 3 h -> +5 kt per 6 h
    assert full.frame["dw_6"].dropna().round(6).eq(5.0).all()


def test_inputs_only_use_past(straight_storm):
    s = build_samples(straight_storm)
    r = s.frame.iloc[5]
    # newest motion = displacement over the 6 h ending at t0 (speed 15 km/h -> 90 km)
    assert np.hypot(r["mx_1"], r["my_1"]) == pytest.approx(90.0, rel=0.02)


def test_missing_targets_are_nan_at_end_of_storm(straight_storm):
    s = build_samples(straight_storm)
    last = s.frame.iloc[-1]
    assert np.isnan(last["dx_72"]) and np.isnan(last["dw_6"])


def test_split_is_event_disjoint(multi_season_tracks):
    parts = split(build_samples(multi_season_tracks))
    sids = [set(p.frame["sid"]) for p in parts.values()]
    assert not (sids[0] & sids[1]) and not (sids[0] & sids[2]) and not (sids[1] & sids[2])


def test_leakage_detector(straight_storm):
    s = build_samples(straight_storm)
    with pytest.raises(AssertionError):
        assert_event_disjoint({"a": s, "b": s})


def test_agency_filter_excludes_other_agencies(straight_storm):
    other = straight_storm.assign(agency="usa", sid="X")
    s = build_samples(pd.concat([straight_storm, other]), agency="newdelhi")
    assert set(s.frame["sid"]) == {straight_storm["sid"].iat[0]}


@pytest.mark.parametrize("model", [RidgeModel(), GBMModel(max_iter=30), PersistenceResidual(RidgeModel())])
def test_models_fit_predict_shapes(multi_season_tracks, model):
    parts = split(build_samples(multi_season_tracks))
    model.fit(parts["train"], parts["val"])
    p = model.predict(parts["test"])
    n, L = len(parts["test"].frame), len(config.load("training")["lead_times_h"])
    assert p["dx"].shape == (n, L) and np.isfinite(p["dw"]).all()


def test_conformal_quantile_finite_sample():
    scores = np.arange(1, 101, dtype=float)
    assert _conf_q(scores, 0.9) == 91.0  # ceil(101*0.9)=91st smallest


def test_conformal_coverage_on_exchangeable_data(multi_season_tracks):
    s = build_samples(multi_season_tracks)
    rng = np.random.default_rng(0)
    m = rng.random(len(s.frame)) < 0.5
    cal_s, test_s = s.subset(m), s.subset(~m)
    model = PersistenceModel()
    cal = ConformalCalibrator().fit(cal_s, model.predict(cal_s))
    p = model.predict(test_s)
    err = track_errors_km(test_s, p)
    r = cal.track_radius(p, 0.9)
    ok = np.isfinite(err)
    assert np.mean(err[ok] <= r[ok]) > 0.8
