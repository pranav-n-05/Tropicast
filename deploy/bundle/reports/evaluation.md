# Evaluation report (auto-generated)

Generated 20261107T113459Z - runtime 219.7 s - fast_mode=False.
All numbers below were computed by `tropicast train`; none are hand-entered.

+pr = model predicts correction to persistence extrapolation.

> Experimental research output. Not an official forecast. Labels: RSMC New Delhi (IMD) best track, 3-min mean winds, via IBTrACS v04r01.

## Dataset
- Data version `ni-91fb4b71781f`; raw sha256 `137d896f68f8dd12...`
- Storms (all agencies, in bbox): 1855; seasons [1842, 2026]

| split | samples | storms | seasons | RI valid | RI positive | RI rate |
|---|---|---|---|---|---|---|
| train | 4432 | 246 | [1982, 2012] | 2915 | 183 | 0.0628 |
| val | 860 | 63 | [2013, 2018] | 615 | 30 | 0.0488 |
| test | 1084 | 81 | [2019, 2025] | 768 | 46 | 0.0599 |

Splits are by season (train 1982-2012, val 2013-2018, test 2019-2025) and are asserted event-disjoint. Training uses every 3-hourly issue time; validation and test use synoptic (00/06/12/18 UTC) issues only.

## Selection (on validation only)
- Track model: **gru_ensemble+pr**
- Intensity model: **gru_ensemble+pr**
- RI model: **ri_logistic+env** (experimental)

## Test - track error
Skill = 1 - error/persistence error on the same samples. CI = 95 % storm-block bootstrap.

| model | lead h | n | mean km | 95% CI | median km | along bias | cross bias | skill % |
|---|---|---|---|---|---|---|---|---|
| persistence | 6 | 1002 | 36.55 | [33.38, 39.56] | 29.7 | -8.02 | -0.0 | 0.0 |
| persistence | 12 | 920 | 71.91 | [65.98, 78.44] | 59.43 | -17.24 | -0.52 | 0.0 |
| persistence | 24 | 768 | 155.1 | [139.05, 171.17] | 130.49 | -42.6 | -4.01 | 0.0 |
| persistence | 48 | 520 | 343.62 | [297.11, 393.74] | 300.6 | -100.12 | -15.38 | 0.0 |
| persistence | 72 | 342 | 531.26 | [442.74, 621.44] | 486.26 | -127.6 | -20.59 | 0.0 |
| ridge+pr | 6 | 1002 | 38.15 | [35.34, 40.78] | 31.76 | -17.61 | 3.97 | -4.37 |
| ridge+pr | 12 | 920 | 74.49 | [68.39, 80.45] | 63.67 | -36.3 | 8.81 | -3.58 |
| ridge+pr | 24 | 768 | 145.74 | [131.45, 160.02] | 124.86 | -80.36 | 15.88 | 6.04 |
| ridge+pr | 48 | 520 | 287.71 | [253.97, 325.64] | 252.66 | -169.1 | 22.87 | 16.27 |
| ridge+pr | 72 | 342 | 395.86 | [348.44, 444.62] | 376.41 | -213.16 | 51.92 | 25.49 |
| gbm | 6 | 1002 | 38.74 | [36.04, 41.39] | 31.78 | -17.52 | 6.04 | -5.99 |
| gbm | 12 | 920 | 76.36 | [70.83, 82.6] | 66.57 | -28.56 | 10.87 | -6.19 |
| gbm | 24 | 768 | 154.16 | [141.29, 167.61] | 138.63 | -63.52 | 19.31 | 0.61 |
| gbm | 48 | 520 | 307.12 | [277.94, 336.3] | 286.57 | -142.77 | 16.69 | 10.62 |
| gbm | 72 | 342 | 478.6 | [411.97, 554.39] | 467.02 | -260.27 | 37.62 | 9.91 |
| gbm+pr | 6 | 1002 | 37.19 | [34.45, 39.76] | 30.09 | -16.67 | 3.42 | -1.75 |
| gbm+pr | 12 | 920 | 74.98 | [69.69, 80.53] | 63.06 | -27.98 | 9.04 | -4.26 |
| gbm+pr | 24 | 768 | 151.19 | [136.84, 165.64] | 133.58 | -60.33 | 15.54 | 2.52 |
| gbm+pr | 48 | 520 | 309.03 | [276.8, 344.98] | 275.61 | -148.83 | 23.19 | 10.07 |
| gbm+pr | 72 | 342 | 476.71 | [420.47, 544.82] | 471.11 | -231.12 | 60.74 | 10.27 |
| gru_ensemble+pr | 6 | 1002 | 37.78 | [34.97, 40.6] | 31.4 | -15.81 | 4.62 | -3.38 |
| gru_ensemble+pr | 12 | 920 | 72.78 | [66.81, 78.8] | 60.48 | -30.83 | 10.5 | -1.2 |
| gru_ensemble+pr | 24 | 768 | 144.05 | [130.75, 157.76] | 126.78 | -73.36 | 19.07 | 7.13 |
| gru_ensemble+pr | 48 | 520 | 293.15 | [259.64, 326.87] | 251.6 | -170.36 | 45.4 | 14.69 |
| gru_ensemble+pr | 72 | 342 | 409.47 | [360.76, 457.54] | 389.47 | -221.9 | 84.69 | 22.93 |
| gbm+pr+env | 6 | 1002 | 36.83 | [33.79, 39.52] | 29.56 | -17.07 | 2.45 | -0.76 |
| gbm+pr+env | 12 | 920 | 74.62 | [68.56, 81.09] | 63.99 | -28.1 | 8.06 | -3.76 |
| gbm+pr+env | 24 | 768 | 147.64 | [134.08, 162.3] | 129.23 | -66.23 | 17.62 | 4.81 |
| gbm+pr+env | 48 | 520 | 305.81 | [273.41, 337.36] | 268.46 | -138.47 | 43.05 | 11.01 |
| gbm+pr+env | 72 | 342 | 422.38 | [371.47, 475.14] | 391.49 | -185.73 | 119.19 | 20.5 |
| gru_ensemble+pr+env | 6 | 1002 | 37.5 | [34.6, 40.46] | 30.86 | -14.64 | 3.94 | -2.61 |
| gru_ensemble+pr+env | 12 | 920 | 71.94 | [65.7, 78.29] | 58.88 | -28.87 | 8.76 | -0.04 |
| gru_ensemble+pr+env | 24 | 768 | 140.5 | [127.35, 153.66] | 120.23 | -65.59 | 20.21 | 9.41 |
| gru_ensemble+pr+env | 48 | 520 | 279.62 | [244.46, 313.49] | 243.51 | -142.17 | 55.23 | 18.63 |
| gru_ensemble+pr+env | 72 | 342 | 402.82 | [345.25, 454.36] | 366.62 | -175.49 | 114.64 | 24.18 |

## Test - intensity (max sustained wind)

| model | lead h | n | MAE kt | RMSE kt | bias kt | skill % |
|---|---|---|---|---|---|---|
| persistence | 6 | 1002 | 3.3 | 5.75 | 0.25 | 0.0 |
| persistence | 12 | 920 | 6.57 | 10.42 | 0.37 | 0.0 |
| persistence | 24 | 768 | 12.45 | 18.41 | 0.17 | 0.0 |
| persistence | 48 | 520 | 20.49 | 29.26 | -2.09 | 0.0 |
| persistence | 72 | 342 | 24.46 | 34.48 | -2.59 | 0.0 |
| ridge+pr | 6 | 1002 | 3.09 | 4.43 | -0.44 | 6.39 |
| ridge+pr | 12 | 920 | 5.74 | 8.18 | -1.06 | 12.58 |
| ridge+pr | 24 | 768 | 10.48 | 14.57 | -1.44 | 15.81 |
| ridge+pr | 48 | 520 | 17.27 | 22.94 | -5.93 | 15.71 |
| ridge+pr | 72 | 342 | 22.01 | 29.07 | -12.76 | 10.0 |
| gbm | 6 | 1002 | 2.84 | 4.79 | -0.85 | 13.75 |
| gbm | 12 | 920 | 4.85 | 7.26 | -0.69 | 26.17 |
| gbm | 24 | 768 | 10.06 | 14.42 | -1.46 | 19.2 |
| gbm | 48 | 520 | 16.94 | 23.77 | -5.0 | 17.32 |
| gbm | 72 | 342 | 19.51 | 27.92 | -8.99 | 20.21 |
| gbm+pr | 6 | 1002 | 2.84 | 4.79 | -0.85 | 13.75 |
| gbm+pr | 12 | 920 | 4.85 | 7.26 | -0.69 | 26.17 |
| gbm+pr | 24 | 768 | 10.06 | 14.42 | -1.46 | 19.2 |
| gbm+pr | 48 | 520 | 16.94 | 23.77 | -5.0 | 17.32 |
| gbm+pr | 72 | 342 | 19.51 | 27.92 | -8.99 | 20.21 |
| gru_ensemble+pr | 6 | 1002 | 3.07 | 4.47 | -0.44 | 7.03 |
| gru_ensemble+pr | 12 | 920 | 5.49 | 8.05 | -0.76 | 16.42 |
| gru_ensemble+pr | 24 | 768 | 9.96 | 14.06 | -0.9 | 19.95 |
| gru_ensemble+pr | 48 | 520 | 16.49 | 22.56 | -5.28 | 19.5 |
| gru_ensemble+pr | 72 | 342 | 19.78 | 26.73 | -8.4 | 19.14 |
| gbm+pr+env | 6 | 1002 | 2.87 | 4.79 | -1.01 | 13.05 |
| gbm+pr+env | 12 | 920 | 5.28 | 7.9 | -1.68 | 19.58 |
| gbm+pr+env | 24 | 768 | 9.68 | 13.84 | -1.88 | 22.22 |
| gbm+pr+env | 48 | 520 | 16.95 | 23.72 | -5.83 | 17.26 |
| gbm+pr+env | 72 | 342 | 19.74 | 27.28 | -9.32 | 19.3 |
| gru_ensemble+pr+env | 6 | 1002 | 3.03 | 4.56 | -0.53 | 8.0 |
| gru_ensemble+pr+env | 12 | 920 | 5.38 | 8.06 | -1.02 | 18.03 |
| gru_ensemble+pr+env | 24 | 768 | 9.76 | 13.97 | -1.25 | 21.59 |
| gru_ensemble+pr+env | 48 | 520 | 15.79 | 21.46 | -4.24 | 22.96 |
| gru_ensemble+pr+env | 72 | 342 | 19.09 | 25.27 | -7.2 | 21.94 |

## Test - calibration of uncertainty (calibrated on validation)
Nominal coverage 67 % and 90 %. Values near nominal = well calibrated.

| model | lead h | track cov67 | r67 km | track cov90 | r90 km | wind cov90 | width90 kt |
|---|---|---|---|---|---|---|---|
| ridge+pr | 6 | 0.753 | 48.2 | 0.916 | 79.64 | 0.92 | 14.07 |
| ridge+pr | 12 | 0.722 | 91.04 | 0.91 | 144.53 | 0.884 | 25.19 |
| ridge+pr | 24 | 0.728 | 181.43 | 0.921 | 283.82 | 0.908 | 48.95 |
| ridge+pr | 48 | 0.825 | 437.42 | 0.944 | 619.48 | 0.927 | 82.35 |
| ridge+pr | 72 | 0.865 | 628.86 | 0.982 | 989.91 | 0.924 | 100.19 |
| gbm | 6 | 0.754 | 49.17 | 0.927 | 83.4 | 0.909 | 12.32 |
| gbm | 12 | 0.711 | 92.9 | 0.913 | 146.79 | 0.911 | 22.43 |
| gbm | 24 | 0.699 | 183.75 | 0.905 | 274.3 | 0.901 | 37.37 |
| gbm | 48 | 0.777 | 419.78 | 0.96 | 631.17 | 0.904 | 63.85 |
| gbm | 72 | 0.86 | 756.78 | 0.982 | 1150.23 | 0.906 | 69.22 |
| gbm+pr | 6 | 0.764 | 48.7 | 0.932 | 82.5 | 0.909 | 12.32 |
| gbm+pr | 12 | 0.729 | 92.13 | 0.914 | 146.52 | 0.911 | 22.43 |
| gbm+pr | 24 | 0.689 | 175.96 | 0.908 | 269.77 | 0.901 | 37.37 |
| gbm+pr | 48 | 0.765 | 424.15 | 0.944 | 606.84 | 0.904 | 63.85 |
| gbm+pr | 72 | 0.854 | 737.4 | 0.971 | 1032.01 | 0.906 | 69.22 |
| gru_ensemble+pr | 6 | 0.733 | 46.51 | 0.935 | 81.45 | 0.907 | 15.87 |
| gru_ensemble+pr | 12 | 0.733 | 89.72 | 0.92 | 147.65 | 0.907 | 25.36 |
| gru_ensemble+pr | 24 | 0.743 | 181.52 | 0.921 | 281.19 | 0.906 | 40.52 |
| gru_ensemble+pr | 48 | 0.765 | 397.0 | 0.923 | 586.22 | 0.9 | 72.77 |
| gru_ensemble+pr | 72 | 0.825 | 598.07 | 0.962 | 987.46 | 0.883 | 88.67 |
| gbm+pr+env | 6 | 0.762 | 47.29 | 0.937 | 84.37 | 0.893 | 11.63 |
| gbm+pr+env | 12 | 0.718 | 88.95 | 0.914 | 146.78 | 0.892 | 20.71 |
| gbm+pr+env | 24 | 0.707 | 177.15 | 0.898 | 265.62 | 0.906 | 38.05 |
| gbm+pr+env | 48 | 0.79 | 426.5 | 0.923 | 616.67 | 0.913 | 71.79 |
| gbm+pr+env | 72 | 0.816 | 619.07 | 0.965 | 951.76 | 0.892 | 66.59 |
| gru_ensemble+pr+env | 6 | 0.759 | 48.55 | 0.93 | 81.91 | 0.882 | 14.75 |
| gru_ensemble+pr+env | 12 | 0.748 | 92.57 | 0.927 | 149.51 | 0.883 | 25.19 |
| gru_ensemble+pr+env | 24 | 0.751 | 182.0 | 0.921 | 279.43 | 0.88 | 38.6 |
| gru_ensemble+pr+env | 48 | 0.798 | 405.27 | 0.937 | 601.56 | 0.877 | 60.27 |
| gru_ensemble+pr+env | 72 | 0.813 | 606.45 | 0.98 | 1030.65 | 0.933 | 84.84 |

## Ablation (available modalities only; GBM)
track = position + motion history; +intensity = wind/pressure history; full adds context (distance to land, month, storm age, sub-basin).

| model | lead h | track km | wind MAE kt |
|---|---|---|---|
| gbm+pr[track] | 6 | 37.27 | 3.12 |
| gbm+pr[track] | 12 | 75.8 | 6.04 |
| gbm+pr[track] | 24 | 154.45 | 11.13 |
| gbm+pr[track] | 48 | 327.66 | 18.43 |
| gbm+pr[track] | 72 | 463.79 | 23.15 |
| gbm+pr[track+intensity] | 6 | 37.61 | 2.77 |
| gbm+pr[track+intensity] | 12 | 75.88 | 5.14 |
| gbm+pr[track+intensity] | 24 | 152.67 | 9.55 |
| gbm+pr[track+intensity] | 48 | 302.24 | 15.93 |
| gbm+pr[track+intensity] | 72 | 461.75 | 20.62 |
| gbm+pr | 6 | 37.19 | 2.84 |
| gbm+pr | 12 | 74.98 | 4.85 |
| gbm+pr | 24 | 151.19 | 10.06 |
| gbm+pr | 48 | 309.03 | 16.94 |
| gbm+pr | 72 | 476.71 | 19.51 |

## Environment ablation (homogeneous test subset with SHIPS predictors, 2019-2021)
env-only = position + current wind + SHIPS t=0 environment (no history). temporal = track + intensity history. Same samples for every row.

| model | lead h | n | track km | track skill % | wind MAE kt | wind skill % |
|---|---|---|---|---|---|---|
| persistence | 6 | 306 | 35.85 | 0.0 | 5.46 | 0.0 |
| persistence | 12 | 292 | 70.49 | 0.0 | 10.67 | 0.0 |
| persistence | 24 | 259 | 156.06 | 0.0 | 19.85 | 0.0 |
| persistence | 48 | 193 | 345.86 | 0.0 | 31.42 | 0.0 |
| persistence | 72 | 135 | 544.43 | 0.0 | 36.48 | 0.0 |
| gbm[env-only] | 6 | 306 | 53.58 | -49.46 | 5.16 | 5.54 |
| gbm[env-only] | 12 | 292 | 99.69 | -41.42 | 8.95 | 16.08 |
| gbm[env-only] | 24 | 259 | 194.52 | -24.64 | 15.04 | 24.21 |
| gbm[env-only] | 48 | 193 | 373.58 | -8.01 | 24.33 | 22.58 |
| gbm[env-only] | 72 | 135 | 434.68 | 20.16 | 27.46 | 24.73 |
| gbm+pr[track+intensity] | 6 | 306 | 37.36 | -4.23 | 4.32 | 20.77 |
| gbm+pr[track+intensity] | 12 | 292 | 74.1 | -5.11 | 7.7 | 27.77 |
| gbm+pr[track+intensity] | 24 | 259 | 152.23 | 2.45 | 13.9 | 29.96 |
| gbm+pr[track+intensity] | 48 | 193 | 325.73 | 5.82 | 22.64 | 27.95 |
| gbm+pr[track+intensity] | 72 | 135 | 538.1 | 1.16 | 29.69 | 18.62 |
| gbm+pr[temporal+env] | 6 | 306 | 36.49 | -1.8 | 4.58 | 16.05 |
| gbm+pr[temporal+env] | 12 | 292 | 69.49 | 1.43 | 7.65 | 28.3 |
| gbm+pr[temporal+env] | 24 | 259 | 143.38 | 8.13 | 15.43 | 22.26 |
| gbm+pr[temporal+env] | 48 | 193 | 300.77 | 13.04 | 23.05 | 26.65 |
| gbm+pr[temporal+env] | 72 | 135 | 420.91 | 22.69 | 27.9 | 23.54 |
| gbm+pr | 6 | 306 | 36.53 | -1.9 | 4.45 | 18.46 |
| gbm+pr | 12 | 292 | 72.43 | -2.76 | 6.95 | 34.8 |
| gbm+pr | 24 | 259 | 149.46 | 4.23 | 14.86 | 25.15 |
| gbm+pr | 48 | 193 | 323.54 | 6.46 | 23.45 | 25.37 |
| gbm+pr | 72 | 135 | 550.05 | -1.03 | 27.62 | 24.29 |
| gbm+pr+env | 6 | 306 | 36.32 | -1.33 | 4.43 | 18.83 |
| gbm+pr+env | 12 | 292 | 68.52 | 2.8 | 6.98 | 34.57 |
| gbm+pr+env | 24 | 259 | 145.07 | 7.04 | 14.1 | 28.93 |
| gbm+pr+env | 48 | 193 | 320.04 | 7.47 | 24.3 | 22.66 |
| gbm+pr+env | 72 | 135 | 438.77 | 19.41 | 28.2 | 22.71 |
| gru_ensemble+pr | 6 | 306 | 36.33 | -1.34 | 4.33 | 20.73 |
| gru_ensemble+pr | 12 | 292 | 69.33 | 1.65 | 7.97 | 25.27 |
| gru_ensemble+pr | 24 | 259 | 142.24 | 8.86 | 14.62 | 26.33 |
| gru_ensemble+pr | 48 | 193 | 290.85 | 15.9 | 22.79 | 27.48 |
| gru_ensemble+pr | 72 | 135 | 416.67 | 23.47 | 26.75 | 26.67 |
| gru_ensemble+pr+env | 6 | 306 | 35.61 | 0.66 | 4.2 | 23.11 |
| gru_ensemble+pr+env | 12 | 292 | 67.4 | 4.38 | 7.55 | 29.19 |
| gru_ensemble+pr+env | 24 | 259 | 135.5 | 13.18 | 14.14 | 28.75 |
| gru_ensemble+pr+env | 48 | 193 | 274.99 | 20.49 | 21.82 | 30.55 |
| gru_ensemble+pr+env | 72 | 135 | 424.35 | 22.06 | 24.71 | 32.28 |

## Rapid intensification (EXPERIMENTAL)

| split | model | n | positives | Brier | Brier clim. | BSS | AUC |
|---|---|---|---|---|---|---|---|
| val | logistic | 615 | 30 | 0.0467 | 0.0466 | -0.002 | 0.652 |
| val | gbm | 615 | 30 | 0.0522 | 0.0466 | -0.12 | 0.726 |
| val | logistic+env | 615 | 30 | 0.0408 | 0.0466 | 0.123 | 0.796 |
| val | gbm+env | 615 | 30 | 0.0531 | 0.0466 | -0.14 | 0.681 |
| test | logistic | 768 | 46 | 0.052 | 0.0563 | 0.077 | 0.771 |
| test | gbm | 768 | 46 | 0.0604 | 0.0563 | -0.072 | 0.712 |
| test | logistic+env | 768 | 46 | 0.0525 | 0.0563 | 0.067 | 0.813 |
| test | gbm+env | 768 | 46 | 0.0609 | 0.0563 | -0.081 | 0.76 |

## Not yet evaluated
- **satellite modalities in the 72 h forecast**: Not combined here - HURSAT ends 2015, so the satellite ablation is a separate study (reports/satellite_evaluation.md).

## Validation tables

| model | lead h | track km | wind MAE kt |
|---|---|---|---|
| persistence | 6 | 43.34 | 3.08 |
| persistence | 12 | 80.21 | 6.13 |
| persistence | 24 | 165.28 | 12.0 |
| persistence | 48 | 360.49 | 21.55 |
| persistence | 72 | 572.35 | 26.32 |
| ridge+pr | 6 | 43.45 | 3.15 |
| ridge+pr | 12 | 79.81 | 5.71 |
| ridge+pr | 24 | 159.69 | 10.53 |
| ridge+pr | 48 | 349.26 | 17.44 |
| ridge+pr | 72 | 533.67 | 20.37 |
| gbm | 6 | 44.19 | 2.71 |
| gbm | 12 | 82.07 | 4.77 |
| gbm | 24 | 160.31 | 10.26 |
| gbm | 48 | 366.04 | 17.93 |
| gbm | 72 | 609.37 | 19.22 |
| gbm+pr | 6 | 42.92 | 2.71 |
| gbm+pr | 12 | 81.03 | 4.77 |
| gbm+pr | 24 | 154.81 | 10.26 |
| gbm+pr | 48 | 361.91 | 17.93 |
| gbm+pr | 72 | 590.66 | 19.22 |
| gru_ensemble+pr | 6 | 42.63 | 3.06 |
| gru_ensemble+pr | 12 | 78.9 | 5.42 |
| gru_ensemble+pr | 24 | 154.1 | 9.8 |
| gru_ensemble+pr | 48 | 328.0 | 16.01 |
| gru_ensemble+pr | 72 | 514.23 | 18.92 |
| gbm+pr+env | 6 | 43.11 | 2.75 |
| gbm+pr+env | 12 | 79.46 | 4.84 |
| gbm+pr+env | 24 | 154.21 | 10.1 |
| gbm+pr+env | 48 | 351.48 | 17.74 |
| gbm+pr+env | 72 | 517.56 | 20.62 |
| gru_ensemble+pr+env | 6 | 42.33 | 3.03 |
| gru_ensemble+pr+env | 12 | 77.89 | 5.22 |
| gru_ensemble+pr+env | 24 | 152.37 | 9.69 |
| gru_ensemble+pr+env | 48 | 327.38 | 16.6 |
| gru_ensemble+pr+env | 72 | 529.76 | 20.09 |
| gbm+pr[track] | 6 | 43.22 | 3.15 |
| gbm+pr[track] | 12 | 81.26 | 6.31 |
| gbm+pr[track] | 24 | 161.0 | 12.52 |
| gbm+pr[track] | 48 | 364.38 | 22.0 |
| gbm+pr[track] | 72 | 551.4 | 25.39 |
| gbm+pr[track+intensity] | 6 | 43.01 | 2.69 |
| gbm+pr[track+intensity] | 12 | 81.26 | 5.3 |
| gbm+pr[track+intensity] | 24 | 162.31 | 10.74 |
| gbm+pr[track+intensity] | 48 | 372.71 | 19.83 |
| gbm+pr[track+intensity] | 72 | 614.91 | 19.84 |
| gbm[env-only] | 6 | 61.29 | 3.1 |
| gbm[env-only] | 12 | 112.23 | 6.05 |
| gbm[env-only] | 24 | 218.04 | 11.06 |
| gbm[env-only] | 48 | 428.07 | 20.05 |
| gbm[env-only] | 72 | 572.79 | 21.11 |
| gbm+pr[temporal+env] | 6 | 43.56 | 2.87 |
| gbm+pr[temporal+env] | 12 | 79.14 | 5.28 |
| gbm+pr[temporal+env] | 24 | 151.73 | 11.07 |
| gbm+pr[temporal+env] | 48 | 349.74 | 19.73 |
| gbm+pr[temporal+env] | 72 | 523.84 | 22.1 |
