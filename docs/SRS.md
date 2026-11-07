# Software Requirements Specification: Tropicast v0.2

Format loosely follows IEEE 29148. The requirement rationale, risks and assumptions are in
[phase1-requirements.md](phase1-requirements.md). This document is the verifiable list. Status values:
**Met** (implemented and tested), **Partial**, **Blocked** (external dependency).

## 1. Purpose and scope
A research decision-support prototype for North Indian Ocean tropical cyclones (Bay of Bengal and Arabian Sea,
0–30°N, 40–100°E). It ingests open data, classifies storms on the IMD scale, issues experimental forecasts with
calibrated uncertainty, estimates intensity from satellite imagery, and estimates coastal exposure. It is **not** an
operational warning system.

## 2. Users
Researchers and students (primary); meteorology analysts (evaluation); disaster-management staff (read-only
context). Every output carries the operational disclaimer.

## 3. Functional requirements
| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR1 | Ingest IBTrACS NI with conditional GET, retry, sha256, provenance manifest | `test_conditional_download_and_manifest`, `test_failed_source_is_recorded_not_raised` | Met |
| FR1b | Ingest SHIPS IO environment (t=0 only) and HURSAT-B1 imagery | `test_ships_reads_only_t0_and_scales`; `tropicast satellite` | Met |
| FR1c | ERA5, IMERG, MOSDAC connectors | scaffold returns `credentials_required` | Blocked (credentials) |
| FR2 | QC: bbox, time, coordinates, spur tracks, duplicates, implausible values; QC report | `test_qc_*`, `reports/data_quality.json` | Met |
| FR3 | Freshness: observation, ingestion and processing time; real_time/recent/delayed/stale/archive labels | `test_freshness_labels`, `test_old_file_never_produces_active_storms` | Met |
| FR4 | Centre localisation from imagery | `reports/localization.json` | Met (research, 1982–2015) |
| FR4b | Cyclone vs non-cyclone detection | needs non-storm scenes | Not feasible with storm-centred archive (documented) |
| FR5 | IMD classification; agency-native values; no silent conversion | `test_thresholds`, `test_agency_mismatch_refused`, `test_agency_preference_and_no_conversion` | Met |
| FR6 | Intensity estimation with uncertainty (satellite CNN) | `reports/satellite_evaluation.md` (nested CV, interval coverage) | Met |
| FR7 | Track forecast 6–72 h with uncertainty cones | `reports/evaluation.md`, API tests | Met |
| FR8 | Intensity forecast and RI probability with documented definition | evaluation reports | Met (RI experimental) |
| FR9 | Explainability: Grad-CAM, ablation (modality contribution), interpretive-aid caveat | `test_cnn_rotation_invariant_tta_and_gradcam`, satellite study | Met |
| FR10 | Historical explorer and model evaluation dashboard | UI | Met |
| FR11 | Inference audit log; model and data versions on every output | `test_audit_log_records_requests`, `test_hindcast_has_uncertainty_versions_and_verification` | Met |
| FR12 | Graceful degradation (source failure, missing env, missing models) | pipeline `partial` status; API 503/422 | Met |
| FR13 | UI separates observed / provisional / official / AI / uncertainty | legend, tags, badges | Met (no official IMD forecast feed; link only) |
| FR14 | Disclaimer on every forecast view and response | `test_storm_list_has_disclaimer` | Met |
| FR15 | Coastal exposure: landfall and strike probability (centre-based) with verification | `reports/landfall_evaluation.json`, landfall tests | Met |
| FR16 | Rainfall footprint | needs IMERG (Earthdata) | Blocked |

## 4. Non-functional requirements
| ID | Requirement | Status |
|---|---|---|
| NFR1 | Reproducible: seeds, versioned configs, data_version hash, regenerated reports | Met |
| NFR2 | No temporal leakage: event/season-disjoint splits asserted; t=0-only environment; nested CV for stacking | Met (tests) |
| NFR3 | CPU-only operation; GPU optional | Met |
| NFR4 | API rate limit (120/min/IP), input validation, no secrets in repo | Met |
| NFR5 | Modular basin configuration (`configs/domain.yaml`) | Met |
| NFR6 | Containerised deployment | Met (`docker compose`) |
| NFR7 | Forecast latency < 60 s per storm on CPU | Met (< 1 s forecast; about 2 s exposure) |

## 5. External interfaces
REST API `/api/v1/*` (see [api.md](api.md) and `/docs` OpenAPI), plus a static web dashboard. Data inputs are listed
in [data_sources.md](data_sources.md).

## 6. Constraints
No fabricated data, endpoints, citations or metrics. Every number in `reports/` is produced by code.
