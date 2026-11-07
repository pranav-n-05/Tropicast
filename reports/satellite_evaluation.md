# Satellite study (auto-generated)

Generated 20261107T120232Z, runtime 1236.4 s, fast_mode=True. Every number below is computed by `tropicast satellite`.

- Images: 3447 from 169 storms, seasons [1982, 2015]
- Nested CV over season blocks [(1982, 1995), (1996, 2001), (2002, 2006), (2007, 2011), (2012, 2015)]
- Common subset (all modalities present): 2338 rows

## A. Intensity estimation (wind at image time, kt)

| configuration | n | MAE | RMSE | bias | MAE per fold |
|---|---|---|---|---|---|
| climatology | 2338 | 16.59 | 23.46 | -4.38 | [17.11, 18.85, 11.84, 16.99, 18.09] |
| sat-only[IR features] | 2338 | 11.68 | 17.19 | -5.45 | [13.75, 13.77, 8.71, 10.76, 12.41] |
| sat-only[CNN] | 2338 | 14.9 | 20.92 | -2.52 | [18.99, 16.03, 9.4, 15.5, 16.09] |
| sat-only[CNN+IR features] | 2338 | 11.78 | 17.46 | -5.57 | [13.69, 14.18, 8.63, 10.97, 12.43] |
| env-only | 2338 | 15.27 | 21.83 | -3.86 | [12.93, 16.68, 9.36, 15.83, 19.36] |
| sat+env | 2338 | 12.24 | 17.62 | -3.67 | [12.48, 14.16, 8.4, 11.93, 14.0] |
| sat+env+temporal | 2338 | 10.88 | 15.99 | -3.94 | [11.37, 12.58, 7.95, 10.52, 12.05] |
| full (+previous best-track wind) | 2338 | 3.74 | 6.24 | -0.65 | [4.37, 4.53, 2.8, 4.08, 3.34] |
| reference: previous wind (t-6 h) | 2338 | 3.98 | 7.38 | -1.01 | [4.84, 4.33, 2.76, 4.21, 4.09] |

Satellite-only on all rows (no environment requirement):

| configuration | n | MAE | RMSE | bias |
|---|---|---|---|---|
| climatology | 3447 | 16.4 | 22.16 | 0.08 |
| sat-only[IR features] | 3447 | 10.24 | 15.84 | -3.4 |
| sat-only[CNN] | 3447 | 14.21 | 19.47 | 0.85 |
| sat-only[CNN+IR features] | 3447 | 10.33 | 16.01 | -3.45 |

CNN 90 % interval (normalised conformal, calibrated on inner out-of-fold residuals):

| fold | coverage | mean width kt |
|---|---|---|
| 0 | 0.871 | 61.9 |
| 1 | 0.883 | 45.3 |
| 2 | 0.902 | 38.2 |
| 3 | 0.963 | 73.1 |
| 4 | 0.859 | 51.6 |

## B. 24-h intensity change forecast (kt), common subset

| configuration | n | MAE | RMSE | bias | RI events predicted >= threshold |
|---|---|---|---|---|---|
| persistence (no change) | 1744 | 15.0 | 21.18 | -4.42 | 0.0 |
| temporal-only | 1744 | 12.78 | 17.59 | -1.52 | 0.03 |
| env-only | 1744 | 13.09 | 18.4 | 0.64 | 0.0 |
| sat-only | 1744 | 13.44 | 19.18 | -2.13 | 0.0 |
| sat+env | 1744 | 12.73 | 18.18 | -0.09 | 0.0 |
| temporal+env | 1744 | 12.19 | 17.1 | 0.08 | 0.006 |
| full (sat+env+temporal) | 1744 | 12.05 | 16.93 | -0.03 | 0.0 |

## C. IMD stage classification from estimated intensity (common subset)

**sat-only[CNN]**: accuracy 0.348, macro-F1 0.294

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 366 | 418 | 137 | 3 |
| CS | 182 | 314 | 192 | 24 |
| SCS | 31 | 114 | 109 | 12 |
| VSCS+ | 18 | 149 | 245 | 24 |

**sat+env+temporal**: accuracy 0.552, macro-F1 0.505

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 674 | 218 | 31 | 1 |
| CS | 226 | 340 | 117 | 29 |
| SCS | 32 | 125 | 103 | 6 |
| VSCS+ | 15 | 89 | 159 | 173 |

**full (+previous best-track wind)**: accuracy 0.82, macro-F1 0.792

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 877 | 43 | 1 | 3 |
| CS | 169 | 493 | 48 | 2 |
| SCS | 1 | 75 | 174 | 16 |
| VSCS+ | 0 | 1 | 61 | 374 |

## Notes
- Labels: RSMC New Delhi 3-min winds. Imagery: HURSAT-B1 v06 IRWIN, best (lowest VZA) satellite.
- Satellite archive ends 2015, so these results are a separate hindcast study, not the live system.
- Common subset = rows with SHIPS environment and a t-6 h best-track wind (1990-2015).
- Explainability (Grad-CAM) is an interpretive aid, not proof of physical causation.
