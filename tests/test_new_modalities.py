"""Tests for SHIPS environment, satellite features/CNN, localisation helpers and landfall exposure."""
import numpy as np
import pandas as pd
import pytest

from tropicast.datasets.samples import attach_env, build_samples
from tropicast.ingestion.ships import ENV_FEATURES, match_to_tracks, parse
from tropicast.satellite.features import IR_FEATURES, ir_features

SHIPS_TXT = (
    " IO01 900417 18   25   10.5   86.4 9999 IO011990" + " " * 68 + "HEAD\n"
    + "".join(f"{v:5d}" for v in [-12, -6, 0, 6, 12] + [9999] * 18) + "TIME\n"
    + "".join(f"{v:5d}" for v in [9999, 9999, 155, 999, 999] + [9999] * 18) + "SHRD\n"
    + "".join(f"{v:5d}" for v in [9999, 9999, 62, 1, 1] + [9999] * 18) + "RHMD\n"
    + "".join(f"{v:5d}" for v in [9999, 9999, 299, 0, 0] + [9999] * 18) + "RSST\n"
    + "".join(f"{v:5d}" for v in [9999, 9999, 150, 0, 0] + [9999] * 18) + "VMPI\n"
)


def test_ships_reads_only_t0_and_scales(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text(SHIPS_TXT)
    d = parse(p)
    assert len(d) == 1
    r = d.iloc[0]
    assert r["time"] == pd.Timestamp("1990-04-17 18:00", tz="UTC")
    assert r["env_shear_kt"] == pytest.approx(15.5)      # t=0 column, /10
    assert r["env_rh_700_500"] == 62                       # not the t=+6 value (1)
    assert r["env_sst_c"] == pytest.approx(29.9)
    assert np.isnan(r["env_ohc_clim"])                     # absent predictor -> NaN


def test_ships_match_requires_proximity(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text(SHIPS_TXT)
    d = parse(p)
    t = pd.DataFrame({"sid": ["A", "B"], "time": [d["time"].iat[0]] * 2, "lat": [10.6, 20.0], "lon": [86.5, 70.0]})
    m = match_to_tracks(d, t)
    assert list(m["sid"]) == ["A"]


def test_env_join_never_uses_future_analysis(straight_storm):
    s = build_samples(straight_storm)
    f = s.frame
    t3 = f.loc[~f["synoptic"], "t0"].iloc[0]          # an off-synoptic issue time
    env = pd.DataFrame({"sid": [f["sid"].iat[0]] * 2,
                        "time": [t3 - pd.Timedelta(hours=3), t3 + pd.Timedelta(hours=3)],
                        "env_shear_kt": [5.0, 40.0], "env_mpi_kt": [150.0, 150.0]})
    out = attach_env(f, env)
    row = out[out["t0"] == t3].iloc[0]
    assert row["env_shear_kt"] == 5.0 and row["env_missing"] == 0.0    # previous analysis, not the later one
    assert row["env_mpi_excess_kt"] == pytest.approx(150.0 - row["wind"])  # uses IMD wind, not SHIPS vmax


def test_env_missing_flag_when_no_env(straight_storm):
    f = attach_env(build_samples(straight_storm).frame, None)
    assert (f["env_missing"] == 1).all() and set(ENV_FEATURES) <= set(f.columns)


def _synthetic_ir(eye=True):
    n = 80
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(yy - 39.5, xx - 39.5) * 15.5
    img = np.where(r < 250, 200.0, 290.0) + r * 0.02
    if eye:
        img[r < 20] = 285.0
    return img.astype(np.float32)


def test_ir_features_detect_warm_eye_and_cold_ring():
    f = dict(zip(IR_FEATURES, ir_features(np.stack([_synthetic_ir(True), _synthetic_ir(False)]),
                                          np.full((2, 80, 80), np.nan))[0]))
    g = dict(zip(IR_FEATURES, ir_features(_synthetic_ir(False)[None], np.full((1, 80, 80), np.nan))[0]))
    assert f["ir_eye_contrast"] > 20 and abs(g["ir_eye_contrast"]) < 5
    assert f["ir_frac220_200"] > 0.9
    assert np.isnan(f["ir_d6_ring_0_30"])  # no previous image


def test_cnn_rotation_invariant_tta_and_gradcam():
    torch = pytest.importorskip("torch")
    from tropicast.satellite.cnn import CNNEstimator
    rng = np.random.default_rng(0)
    imgs = np.stack([_synthetic_ir(rng.random() > 0.5) + rng.normal(0, 2, (80, 80)) for _ in range(24)])
    y = rng.uniform(25, 100, 24)
    c = CNNEstimator(members=1, epochs=1, batch_size=8).fit(imgs, y)
    p = c.predict(imgs[:3], tta=4)
    assert p["mean"].shape == (3,) and (p["sd"] > 0).all() and p["embedding"].shape[0] == 3
    cam = c.gradcam(imgs[0])
    assert cam.shape == (64, 64) and 0 <= cam.min() and cam.max() <= 1.0 + 1e-6
    st = CNNEstimator.from_state(c.state())
    np.testing.assert_allclose(st.predict(imgs[:2], tta=2)["mean"], c.predict(imgs[:2], tta=2)["mean"], rtol=1e-5)


def test_centre_crop_labels_consistent():
    from tropicast.satellite.localization import CROP, _crops
    img = np.full((1, 80, 80), 280.0, np.float32)
    img[0, 39:41, 39:41] = 190.0  # cold dot at the true centre
    x, c = _crops(np.repeat(img, 20, 0), np.random.default_rng(1))
    for xi, ci in zip(x, c):
        yx = np.argwhere(xi < 200).mean(0) + 0.5
        assert np.allclose([yx[1], yx[0]], ci, atol=1.0)
    assert x.shape[-1] == CROP


def test_landfall_member_sigma_matches_radius():
    from tropicast.risk.landfall import SIGMA_PER_R90, _members
    rng = np.random.default_rng(0)
    hours, hl, ho = _members(15.0, 88.0, np.array([15.0]), np.array([88.0]), [300.0], [24], 4000, 0.8, rng)
    from tropicast.geospatial.geo import haversine_km
    d = haversine_km(15.0, 88.0, hl[:, -1], ho[:, -1])
    assert np.mean(d <= 300.0) == pytest.approx(0.9, abs=0.02)   # r90 contains ~90 % of members
    assert SIGMA_PER_R90 == pytest.approx(1 / 2.146, rel=1e-3)


def test_observed_landfall_logic():
    from tropicast.risk.landfall import observed_landfall
    t = pd.date_range("2020-05-18", periods=13, freq="6h", tz="UTC")
    g = pd.DataFrame({"time": t, "dist2land_km": [300, 250, 200, 150, 100, 50, 0, 0, 0, 0, 0, 0, 0]})
    assert observed_landfall(g, t[0]) is True
    assert observed_landfall(g, t[7]) is None          # already over land
    g2 = g.assign(dist2land_km=400)
    assert observed_landfall(g2, t[0]) is False
