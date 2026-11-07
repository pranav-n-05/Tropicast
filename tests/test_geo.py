import numpy as np
import pytest

from tropicast.geospatial.geo import (along_cross_track_error, destination, displacement_to_km, haversine_km,
                                      initial_bearing_deg, km_to_displacement)


def test_one_degree_latitude():
    assert haversine_km(10, 85, 11, 85) == pytest.approx(111.19, abs=0.05)


def test_destination_roundtrip():
    lat, lon = destination(15.0, 85.0, 45.0, 500.0)
    assert haversine_km(15.0, 85.0, lat, lon) == pytest.approx(500.0, rel=1e-6)
    assert initial_bearing_deg(15.0, 85.0, lat, lon) == pytest.approx(45.0, abs=1e-6)


def test_local_displacement_inverse():
    dx, dy = displacement_to_km(12.0, 86.0, 14.0, 84.5)
    lat, lon = km_to_displacement(12.0, 86.0, dx, dy)
    assert lat == pytest.approx(14.0, abs=0.01) and lon == pytest.approx(84.5, abs=0.01)


def test_along_cross_signs():
    # storm moved due north 100 km; forecast 50 km further north and 30 km east (right of motion)
    olat, olon = destination(10.0, 85.0, 0.0, 100.0)
    flat, flon = destination(olat, olon, 0.0, 50.0)
    flat, flon = destination(flat, flon, 90.0, 30.0)
    al, cr = along_cross_track_error(10.0, 85.0, olat, olon, flat, flon)
    assert al == pytest.approx(50.0, abs=1.0)
    assert cr == pytest.approx(30.0, abs=1.0)


def test_along_cross_stationary_is_nan():
    al, cr = along_cross_track_error(10.0, 85.0, 10.0, 85.0, 10.5, 85.0)
    assert np.isnan(al) and np.isnan(cr)
