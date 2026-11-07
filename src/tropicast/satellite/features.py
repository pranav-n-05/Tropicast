"""Hand-crafted IR structure features (interpretable, Dvorak-inspired).

Pixel spacing after preprocessing: 0.14 deg (~15.5 km at the equator, Mercator
grid; latitude distortion < 5 % in the NIO and ignored). Features per image:
* azimuthal-mean BT in radial rings (0-30, 30-60, 60-100, 100-200, 200-300 km)
* minimum BT and 10th percentile BT within 100 km
* fraction of pixels colder than 220 K / 200 K within 200 km (deep convection)
* eye proxy: centre BT (0-30 km) minus ring BT (30-100 km) - warm eye => positive
* asymmetry: std of quadrant-mean BT within 200 km
* BT change of ring means vs t-6 h image (temporal IR), NaN when unavailable
"""
from __future__ import annotations

import numpy as np

PX_KM = 15.5
_N = 80
_yy, _xx = np.mgrid[0:_N, 0:_N]
_R = np.hypot(_yy - (_N - 1) / 2, _xx - (_N - 1) / 2) * PX_KM
_Q = (np.arctan2(_yy - (_N - 1) / 2, _xx - (_N - 1) / 2) // (np.pi / 2)).astype(int) % 4
RINGS = [(0, 30), (30, 60), (60, 100), (100, 200), (200, 300)]
IR_FEATURES = ([f"ir_ring_{a}_{b}" for a, b in RINGS] + ["ir_min_100", "ir_p10_100", "ir_frac220_200",
               "ir_frac200_200", "ir_eye_contrast", "ir_asym_200"] +
               [f"ir_d6_ring_{a}_{b}" for a, b in RINGS[:4]])


def _one(img: np.ndarray) -> list[float]:
    f = [float(np.mean(img[(_R >= a) & (_R < b)])) for a, b in RINGS]
    r100, r200 = _R < 100, _R < 200
    f += [float(img[r100].min()), float(np.percentile(img[r100], 10)), float(np.mean(img[r200] < 220)),
          float(np.mean(img[r200] < 200))]
    f.append(float(np.mean(img[_R < 30]) - np.mean(img[(_R >= 30) & (_R < 100)])))
    f.append(float(np.std([img[r200 & (_Q == q)].mean() for q in range(4)])))
    return f


def ir_features(images: np.ndarray, prev6: np.ndarray) -> np.ndarray:
    out = []
    for img, p in zip(images, prev6):
        f = _one(img)
        if np.isnan(p).all():
            f += [np.nan] * 4
        else:
            f += [f[i] - float(np.mean(p[(_R >= a) & (_R < b)])) for i, (a, b) in enumerate(RINGS[:4])]
        out.append(f)
    return np.asarray(out, dtype=np.float32)
