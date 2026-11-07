"""Spherical-earth geodesy helpers (vectorised, numpy).

Uses a mean earth radius of 6371.0088 km. Errors of the spherical approximation
versus WGS84 are < 0.5 %, negligible relative to cyclone track errors.
"""
from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088
KM_PER_NMI = 1.852


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between points (degrees)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def initial_bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2, degrees clockwise from north [0, 360)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    x = np.sin(dlmb) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dlmb)
    return (np.degrees(np.arctan2(x, y)) + 360.0) % 360.0


def destination(lat, lon, bearing_deg, distance_km):
    """Point reached from (lat, lon) travelling ``distance_km`` along ``bearing_deg``."""
    p1 = np.radians(lat)
    l1 = np.radians(lon)
    th = np.radians(bearing_deg)
    d = np.asarray(distance_km) / EARTH_RADIUS_KM
    p2 = np.arcsin(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(th))
    l2 = l1 + np.arctan2(np.sin(th) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return np.degrees(p2), (np.degrees(l2) + 540.0) % 360.0 - 180.0


def displacement_to_km(lat0, lon0, lat1, lon1):
    """Local east/north displacement (km) from point 0 to point 1 (equirectangular)."""
    mean_lat = np.radians((np.asarray(lat0) + np.asarray(lat1)) / 2)
    dx = np.radians(np.asarray(lon1) - np.asarray(lon0)) * np.cos(mean_lat) * EARTH_RADIUS_KM
    dy = np.radians(np.asarray(lat1) - np.asarray(lat0)) * EARTH_RADIUS_KM
    return dx, dy


def km_to_displacement(lat0, lon0, dx_km, dy_km):
    """Inverse of :func:`displacement_to_km` (first-order, adequate for < ~1500 km)."""
    lat1 = np.asarray(lat0) + np.degrees(np.asarray(dy_km) / EARTH_RADIUS_KM)
    mean_lat = np.radians((np.asarray(lat0) + lat1) / 2)
    lon1 = np.asarray(lon0) + np.degrees(np.asarray(dx_km) / (EARTH_RADIUS_KM * np.cos(mean_lat)))
    return lat1, lon1


def along_cross_track_error(lat_prev, lon_prev, lat_obs, lon_obs, lat_fc, lon_fc):
    """Along- and cross-track components (km) of a forecast error.

    The reference direction is the observed storm motion from ``prev`` to ``obs``.
    Positive along-track = forecast ahead of observed (too fast); positive
    cross-track = forecast right of observed motion.
    """
    mx, my = displacement_to_km(lat_prev, lon_prev, lat_obs, lon_obs)
    ex, ey = displacement_to_km(lat_obs, lon_obs, lat_fc, lon_fc)
    norm = np.hypot(mx, my)
    norm = np.where(norm < 1e-6, np.nan, norm)
    ux, uy = mx / norm, my / norm
    along = ex * ux + ey * uy
    cross = ex * uy - ey * ux  # right-hand normal (ux, uy) -> (uy, -ux)
    return along, cross
