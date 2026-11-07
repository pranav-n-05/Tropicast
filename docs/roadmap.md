# Project progress register

## Completed
- Phase 1: requirements (docs/phase1-requirements.md)
- Phase 3: system design for the v0.1 scope (docs/architecture.md)
- Phase 4: IBTrACS connector; credential scaffolds for ERA5, IMERG, MOSDAC and Himawari
- Phase 5–6: QC, tidy tracks, versioned dataset, leakage-safe samples, season split
- Phase 7–8: persistence, ridge, GBM, GRU ensemble and RI models; conformal uncertainty; evaluation and ablation
  (track-based modalities only)
- Phase 9–11: FastAPI, dashboard, real-time pipeline, audit log
- Phase 12: 55 automated tests (unit, integration, API)
- Phase 13: Dockerfile and compose file (written; image build not yet run because the Docker daemon was not running)

## Partial / pending
- Phase 2: full literature review (only a methods reference list exists)
- Satellite modalities, detection, eye segmentation, Grad-CAM: blocked on MOSDAC/INSAT access
- Environmental ablation: blocked on an ERA5 key
- MLflow tracking, PostGIS, React port: deferred (see the deviations in architecture.md)

## Next tasks, by expected value
1. Get ERA5 access and add shear, mid-level RH, SST and steering flow at t0. Re-run the ablation
   (track vs track+environment).
2. Apply for MOSDAC access. Train a CNN intensity estimator on INSAT IR, starting from Pradhan et al. 2018.
3. Add a low-latency position feed (JTWC/IMD bulletins, subject to terms) so the system becomes truly real-time.
4. Address the slow along-track bias: try lead-specific models, test motion-climatology features, and check for
   train/test era drift.
5. Recalibrate RI with environmental predictors; report reliability diagrams in the UI.
