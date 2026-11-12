# Satellite study (auto-generated)

Generated 20261107T123603Z, runtime 1968.1 s, fast_mode=False. Every number below is computed by `tropicast satellite`.

- Images: 3447 from 169 storms, seasons [1982, 2015]
- Nested CV over season blocks [(1982, 1995), (1996, 2001), (2002, 2006), (2007, 2011), (2012, 2015)]
- Common subset (all modalities present): 2338 rows

## A. Intensity estimation (wind at image time, kt)

| configuration | n | MAE | RMSE | bias | MAE per fold |
|---|---|---|---|---|---|
| climatology | 2338 | 16.59 | 23.46 | -4.38 | [17.11, 18.85, 11.84, 16.99, 18.09] |
| sat-only[IR features] | 2338 | 11.68 | 17.19 | -5.45 | [13.75, 13.77, 8.71, 10.76, 12.41] |
| sat-only[CNN] | 2338 | 12.84 | 19.15 | -4.43 | [14.97, 12.7, 9.2, 12.63, 15.07] |
| sat-only[CNN+IR features] | 2338 | 11.31 | 16.61 | -4.82 | [13.12, 12.95, 8.56, 10.65, 12.07] |
| env-only | 2338 | 15.27 | 21.83 | -3.86 | [12.93, 16.68, 9.36, 15.83, 19.36] |
| sat+env | 2338 | 11.81 | 16.98 | -2.85 | [12.04, 13.05, 8.12, 11.87, 13.66] |
| sat+env+temporal | 2338 | 10.33 | 14.82 | -2.04 | [11.35, 11.51, 7.2, 10.31, 11.5] |
| full (+previous best-track wind) | 2338 | 3.77 | 6.24 | -0.64 | [4.68, 4.48, 2.78, 4.12, 3.32] |
| reference: previous wind (t-6 h) | 2338 | 3.98 | 7.38 | -1.01 | [4.84, 4.33, 2.76, 4.21, 4.09] |

Satellite-only on all rows (no environment requirement):

| configuration | n | MAE | RMSE | bias |
|---|---|---|---|---|
| climatology | 3447 | 16.4 | 22.16 | 0.08 |
| sat-only[IR features] | 3447 | 10.24 | 15.84 | -3.4 |
| sat-only[CNN] | 3447 | 11.4 | 17.32 | -2.02 |
| sat-only[CNN+IR features] | 3447 | 9.87 | 15.15 | -2.95 |

CNN 90 % interval (normalised conformal, calibrated on inner out-of-fold residuals):

| fold | coverage | mean width kt |
|---|---|---|
| 0 | 0.884 | 52.2 |
| 1 | 0.95 | 60.7 |
| 2 | 0.914 | 49.2 |
| 3 | 0.943 | 52.6 |
| 4 | 0.869 | 53.1 |

## B. 24-h intensity change forecast (kt), common subset

| configuration | n | MAE | RMSE | bias | RI events predicted >= threshold |
|---|---|---|---|---|---|
| persistence (no change) | 1744 | 15.0 | 21.18 | -4.42 | 0.0 |
| temporal-only | 1744 | 12.78 | 17.59 | -1.52 | 0.03 |
| env-only | 1744 | 13.09 | 18.4 | 0.64 | 0.0 |
| sat-only | 1744 | 13.19 | 18.94 | -1.99 | 0.0 |
| sat+env | 1744 | 12.67 | 17.99 | -0.17 | 0.006 |
| temporal+env | 1744 | 12.19 | 17.1 | 0.08 | 0.006 |
| full (sat+env+temporal) | 1744 | 12.04 | 16.93 | 0.01 | 0.024 |

## C. IMD stage classification from estimated intensity (common subset)

**sat-only[CNN]**: accuracy 0.467, macro-F1 0.41

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 630 | 234 | 46 | 14 |
| CS | 297 | 257 | 130 | 28 |
| SCS | 54 | 107 | 83 | 22 |
| VSCS+ | 50 | 110 | 155 | 121 |

**sat+env+temporal**: accuracy 0.547, macro-F1 0.509

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 652 | 241 | 29 | 2 |
| CS | 200 | 309 | 162 | 41 |
| SCS | 20 | 118 | 97 | 31 |
| VSCS+ | 10 | 70 | 135 | 221 |

**full (+previous best-track wind)**: accuracy 0.816, macro-F1 0.787

| true \ predicted | D/DD | CS | SCS | VSCS+ |
|---|---|---|---|---|
| D/DD | 873 | 47 | 1 | 3 |
| CS | 166 | 489 | 55 | 2 |
| SCS | 0 | 77 | 173 | 16 |
| VSCS+ | 0 | 1 | 62 | 373 |

## Notes
- Labels: RSMC New Delhi 3-min winds. Imagery: HURSAT-B1 v06 IRWIN, best (lowest VZA) satellite.
- Satellite archive ends 2015, so these results are a separate hindcast study, not the live system.
- Common subset = rows with SHIPS environment and a t-6 h best-track wind (1990-2015).
- Explainability (Grad-CAM) is an interpretive aid, not proof of physical causation.
