# Research paper outline

**Working title:** *Open, calibrated, multimodal machine-learning baselines for tropical cyclone track, intensity and
landfall prediction in the North Indian Ocean*

**Target venues:** *Weather and Forecasting*, *Artificial Intelligence for the Earth Systems* (AMS), *MAUSAM*,
*Natural Hazards*. Check the scope of each before submission.

## Abstract (≈250 words)
Problem: there are few open, leakage-safe NIO baselines, and forecast uncertainty is rarely calibrated. Data: RSMC New
Delhi best track (IBTrACS), SHIPS IO predictors, HURSAT-B1 IR. Methods: persistence-residual GBM and GRU ensembles,
a CNN on IR, conformal calibration, and nested season-block CV for the modality ablation. Key results: insert from
`reports/*.md` at submission time; no numbers are written into this outline. Availability: code and reports
regenerate every number.

## 1. Introduction
- NIO impact (Bay of Bengal storm surge, Arabian Sea trends); forecasting challenges (small sample, monsoon
  regimes, RI).
- Gaps (docs/literature.md §7): reproducibility, calibration, modality attribution, agency conventions.
- Contributions:
  1. leakage-safe benchmark with event-disjoint splits;
  2. calibrated uncertainty, verified per lead;
  3. satellite × environment × temporal ablation;
  4. verified landfall probabilities;
  5. open platform.

## 2. Data
- 2.1 Best track: RSMC New Delhi via IBTrACS; 3-min winds; QC; agency handling.
- 2.2 SHIPS IO predictors: t=0 only; matching method; perfect-prognosis caveat.
- 2.3 HURSAT-B1 IR: VZA selection; preprocessing; satellite eras.
- 2.4 Splits: seasons 1982–2012 / 2013–2018 / 2019–2025 (tracks); five season blocks (imagery).

## 3. Methods
- 3.1 Reference models: persistence; CLIPER-style ridge.
- 3.2 Persistence-residual learning (GBM, GRU ensemble with Gaussian NLL).
- 3.3 Satellite CNN (rotation augmentation, no mirroring, test-time augmentation); hand-crafted IR features;
  concatenation fusion with nested out-of-fold stacking.
- 3.4 Uncertainty: split conformal (normalised for ensembles), CQR for wind.
- 3.5 RI classification (≥ 30 kt / 24 h; Kotal & Roy Bhowmik 2013 convention); proper scoring.
- 3.6 Landfall/strike probabilities from AR(1)-correlated member tracks drawn from calibrated cones.
- 3.7 Centre localisation (DSNT heatmap).
- 3.8 Verification: great-circle, along/cross-track, MAE/RMSE/bias, coverage, Brier/BSS/AUC/reliability,
  storm-block bootstrap CIs.

## 4. Results
Tables and figures come from reports/:
- T1 track errors by lead, with skill vs persistence and CIs (evaluation.md)
- T2 intensity MAE by lead
- T3 environment ablation on the homogeneous subset
- T4 satellite estimation ablation (satellite_evaluation.md §A)
- T5 24 h intensity-change ablation (§B)
- T6 stage confusion matrices (§C)
- T7 RI scores and reliability
- T8 landfall verification (landfall_evaluation.json)
- T9 centre localisation vs baselines (localization.json)
- F1 coverage vs nominal per lead
- F2 reliability diagrams (RI, landfall)
- F3 Grad-CAM examples (Amphan, Fani, Gonu)
- F4 case studies (Amphan 2020 RI, Gonu 2007 Arabian Sea)

## 5. Discussion
- Where ML beats persistence (≥ 24 h) and where it does not (6–12 h). The slow along-track bias and possible causes
  (era drift, steering-flow information missing from history).
- Value of the environment vs imagery; best-track label noise as a ceiling (Dvorak dependence).
- Landfall over-forecasting at low probabilities; calibration options.
- Limits: HURSAT ends 2015; SHIPS ends 2021; no wind field, surge or rain.

## 6. Conclusions and future work
INSAT-3D/3DR via MOSDAC, ERA5 steering flow, ConvLSTM on sequences, physics-informed constraints, operational
latency.

## Reproducibility statement
Commands: `tropicast ingest && tropicast train && tropicast satellite && tropicast risk-eval`; seeds and configs are in
`configs/`; data versions are hashed.
