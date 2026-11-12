# Testing report (Phase 12)

Run on 2026-11-07, macOS arm64, Python 3.13, CPU only. Command: `python -m pytest -q`. **Result: 71 passed, 0 failed.**

| file | tests | covers |
|---|---|---|
| test_geo.py | 5 | haversine, destination round trip, local displacement inverse, along/cross-track signs, stationary edge case |
| test_imd.py | 19 | every IMD threshold boundary, fractional winds, agency-mismatch refusal, unknown wind, probability normalisation |
| test_preprocessing.py | 4 | agency preference without conversion, QC drops (bbox, time, spur), implausible values → NaN, synoptic filter |
| test_samples_models.py | 11 | target construction, inputs use the past only, missing targets, event-disjoint split, leakage detector, agency filter, model shapes, finite-sample conformal quantile, coverage on exchangeable data |
| test_pipeline_ingestion.py | 10 | conditional download + manifest, failure recorded not raised, freshness labels, stale files never produce active storms, notification deduplication |
| test_new_modalities.py | 9 | SHIPS reads t=0 only + scaling, proximity matching, env join never uses a future analysis, env-missing flag, IR eye/cold-ring features, CNN TTA/Grad-CAM/state round trip, localisation crop labels, landfall σ vs r90, observed-landfall logic |
| test_api.py | 9 | health, disclaimer present, hindcast uncertainty/versions/verification, 404, 422, audit log, honest source status, satellite product at a requested time, exposure endpoint |
| test_security.py | 4 | rate limit → 429, report allow-list blocks path traversal, no secrets in source/config, UI escapes untrusted strings |

## Other testing
| type | method | result |
|---|---|---|
| Geospatial validation | bbox/coordinate QC counts in `reports/data_quality.json`; geodesy unit tests | pass |
| Data quality | QC report: 5,149 outside bbox, 78 spur rows dropped; implausible values set to NaN | documented |
| Model testing | season-disjoint test sets; coverage, Brier, AUC, CIs in reports | see reports/ |
| Missing-data testing | env-missing flag tests; forecasts for JTWC-only storms withhold IMD outputs; pipeline `partial` status | pass |
| Real-time pipeline | `tropicast pipeline --once` on live IBTrACS: 1 active storm (MURASU), forecast stored, status ok | pass |
| Performance | `scripts/perf_test.py` → `reports/performance.json`: forecast p50 18 ms, exposure (300 members) p50 192 ms, satellite + Grad-CAM p50 45 ms | meets NFR7 |
| Deployment | `docker build` → `tropicast:0.2` (1.92 GB); container served health, hindcast and dashboard on :8001 | pass |
| UI | manual browser check: map, cones, hindcast slider, exposure, satellite panel with Grad-CAM, Models tab | pass |

## Defects found by testing and fixed
1. `attach_env` created duplicate `_x`/`_y` columns when called on a frame that already had env columns. Found by
   `test_env_join_never_uses_future_analysis`.
2. SHIPS parser failed when a predictor line was absent. Found by `test_ships_reads_only_t0_and_scales`.
3. The coldest-cloud localisation baseline used zero padding, which biased its argmin towards image edges (590 km →
   176 km after the fix). Found by a plausibility review of the results.
4. The satellite endpoint returned 500 when a time was passed (numpy object array minus Timestamp). Found in a UI
   check; regression test added.
5. A browser cached a stale `app.js` after deployment. Fixed with versioned asset URLs.
