# Project progress register

## Completed phases
| phase | status | evidence |
|---|---|---|
| 1 Requirements | done | docs/phase1-requirements.md, docs/SRS.md |
| 2 Literature review | done | docs/literature.md (verified citations, gap analysis) |
| 3 System design | done | docs/architecture.md (layers, DFD, UML, sequences, ER, wireframe, config, errors, versioning) |
| 4 Data collection | done | IBTrACS, SHIPS IO, HURSAT-B1, Natural Earth connectors; scaffolds for ERA5/IMERG/MOSDAC |
| 5 Preprocessing | done | QC, agency-explicit tracks, image pipeline, data-quality report |
| 6 Dataset engineering | done | docs/datasets.md; leakage tests |
| 7 Model development | done | forecast models, RI, satellite CNN, fusion, localisation, landfall |
| 8 Evaluation | done | reports/evaluation.md, satellite_evaluation.md, landfall_evaluation.json, localization.json |
| 9 Backend | done | FastAPI, 16 endpoints |
| 10 Frontend | done | dashboard |
| 11 Real-time | done | pipeline, freshness, notifications/webhook |
| 12 Testing | done | docs/testing_report.md (71 tests) |
| 13 Deployment | done | Docker image built and smoke-tested |
| 14 Documentation | done | full docs set + generated final report |

## Model versions
See `artifacts/registry.json` (track/intensity/RI) and `artifacts/satellite_cnn.pt`. Version ids are embedded in
every API payload.

## Known issues / limits
- Satellite (HURSAT, ends 2015) and environment (SHIPS, ends 2021) are not available for live storms. Live
  forecasts fall back to track-only behaviour, and this is labelled in the payload.
- IBTrACS latency is days, so live storms are usually `recent`, not `real_time`.
- Landfall probabilities over-forecast in the 0.1–0.3 range (reliability table). Recalibration (e.g. isotonic on
  validation) is a candidate.
- Cyclone-vs-non-cyclone detection is not feasible with a storm-centred archive.

## Next tasks (by expected value)
1. MOSDAC access → retrain the CNN on INSAT-3D/3DR (same pipeline) and run it live.
2. ERA5 or a GFS analysis feed for live environment features (steering flow, shear) in real time.
3. Isotonic recalibration of landfall and RI probabilities on validation data.
4. ConvLSTM over IR sequences once more imagery is available; physics-informed motion constraints.
5. IMD bulletin parsing (subject to terms) for an official-forecast overlay and lower latency.
