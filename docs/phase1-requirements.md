# Phase 1: Requirement Analysis — North Indian Ocean Cyclone Intelligence Platform

## Context
Project dir `/Users/pranavneelakandan/Tropicast` is empty (verified). No code exists. The master prompt requires Phase 1 to be a requirements deliverable only, with no application code, followed by an approval gate before Phase 2. This plan = the Phase 1 document. On approval I will write it to `docs/phase1-requirements.md` and scaffold only the `docs/` folder (no source code).

Legend: **[V]** verified from the prompt/general well-known fact, **[A]** assumption, **[R]** requires verification before use.

## 1. Problem statement
Operational cyclone monitoring in the North Indian Ocean (NIO) relies on a few agencies and manual analysis (e.g. Dvorak-type workflows). Research-grade tooling that fuses multi-source satellite, atmospheric, oceanic and precipitation data with ML — and reports calibrated uncertainty — is not readily available as one integrated, reproducible system. Goal: build a research, decision-support prototype that detects, classifies, estimates, tracks and forecasts NIO tropical cyclones with explicit uncertainty, provenance and freshness reporting. It is not an official warning product.

## 2. Vision and objectives
Ten objectives from prompt §3, grouped into delivery tiers:
- **Tier A (core, must ship):** O1 multi-source ingestion/harmonisation, O5 track forecast, O4 intensity estimation, O3 classification (IMD categories), O10 real-time monitoring, O8 uncertainty/disclaimers.
- **Tier B (should ship):** O2 detection/centre localisation, O6 intensity forecast (RI as experimental), O9 explainability.
- **Tier C (stretch, gated by data):** O7 deep environmental analysis (OHC, shear studies), O8 rainfall footprint / coastal exposure.

## 3. Geographical scope
- Bay of Bengal + Arabian Sea only. **[A]** Working bounding box ≈ 0°–30°N, 40°E–100°E (to be fixed in config `configs/domain.yaml`; includes Gulf of Aden/Oman approaches and Andaman Sea). Open question Q1.
- Basin-specific values (bbox, agency, category table) live in config, not code → later basin addition without redesign.

## 4. Functional requirements (summary, FR-ID per line in final doc)
FR1 ingest per-source connectors (config endpoints, auth, retry, checksum, incremental, failure isolation, versioning).
FR2 harmonise: reprojection, resampling, time sync, QC flags, bbox/timestamp validation, provenance.
FR3 freshness: show observation / ingestion / processing timestamps, latency, freshness status; never label stale data "real-time".
FR4 detect cyclonic systems + centre localisation.
FR5 classify per IMD categories; keep agency-native values and conventions.
FR6 estimate max sustained wind and min central pressure, with uncertainty.
FR7 track + forecast position at 6/12/24/48/72 h with uncertainty cone.
FR8 forecast intensity + RI probability (calibrated) with documented RI definition.
FR9 explainability (Grad-CAM, modality contribution, sensitivity) with "interpretive aid" caveat.
FR10 historical explorer (IBTrACS-based) and model evaluation dashboard.
FR11 inference audit log; model/dataset version IDs on every output.
FR12 graceful degradation with explicit fallback/missing-input status.
FR13 dashboard visually separating: observed / official / experimental AI / historical / uncertainty.
FR14 prominent safety disclaimer on every forecast view.

## 5. Non-functional requirements
Reproducibility (seeded, versioned configs/data/models, MLflow); modularity (per-layer packages per §9 tree); CPU-first dev with optional GPU; observability (structured logs, health checks, source-status endpoint); security (secrets via env, rate limiting, input validation); licensing compliance per source; accessibility/responsiveness for UI; maintainability (type hints, docstrings, tests). Latency targets **[A]**: dashboard refresh within one ingestion cycle; inference < 60 s/system on CPU for single-storm run. Open question Q5.

## 6. Stakeholders
Researchers/students (primary users, **[A]** project author is also primary dev); meteorology analysts (evaluators); disaster-management reviewers (consumers of outputs, risk of misuse); data providers (IMD/MOSDAC, NOAA, ECMWF/Copernicus, NASA) — licence compliance; supervisors/reviewers (scientific rigor). Key risk stakeholder: general public — mitigated by disclaimer and non-operational framing.

## 7. Use cases
UC1 monitor live basin map + data freshness. UC2 inspect active system: detection, class, intensity ± uncertainty. UC3 view experimental track/intensity forecast with cone and RI probability. UC4 explore historical storms and compare AI hindcast vs best track. UC5 review model evaluation and ablations. UC6 explain a prediction. UC7 admin: check source status, model versions, audit log. UC8 researcher: reproduce a dataset/model build from config.

## 8. Data-source feasibility (no endpoints asserted; all URLs/access confirmed in Phase 2/4)
| Source | Role | Access (belief) | Status |
|---|---|---|---|
| NOAA IBTrACS | best-track labels, includes IMD (RSMC New Delhi) agency fields for NIO | Public download, no auth | [V] exists; exact version/fields/wind-averaging [R] |
| IMD cyclone reports | official categories, advisories | Public reports; machine-readable access [R] | likely manual/PDF |
| ISRO MOSDAC (INSAT-3D/3DR) | primary regional IR/VIS/WV imagery | Registration required; bulk/API access terms [R] | highest-value, highest-risk |
| Himawari-8/9 | supplementary imagery | Public via JMA/NOAA/AWS mirrors [R]; coverage of Arabian Sea poor, Bay of Bengal at view-angle edge [R] | supplementary only |
| EUMETSAT Meteosat (IODC) | alternative Indian Ocean imagery | Registration [R] | candidate fallback if MOSDAC blocked |
| NOAA HURSAT | historical storm-centred imagery for training | Public [V]; temporal coverage and NIO inclusion [R] | candidate for training set |
| ERA5 (Copernicus CDS) | atmosphere: shear, humidity, SLP, winds, vorticity | Free account + API key [V]; ~5-day latency for ERA5T [R] | historical/training; not truly real-time |
| Operational NWP analysis (e.g. GFS) | near-real-time environment | Public [R] | real-time stand-in for ERA5 |
| NASA GPM IMERG | precipitation | Earthdata login [V]; Early/Late/Final latencies [R] | use Early for NRT |
| SST (e.g. OISST/GHRSST) , OHC (altimetry/ocean reanalysis) | ocean state | [R] product choice | OHC likely Tier C |
| Scatterometer/microwave | wind/structure | [R] | Tier C |

Key feasibility finding: real-time INSAT access is the single biggest dependency. Fallback ladder: MOSDAC → Meteosat-IODC → Himawari (partial) → historical-replay mode (simulated "live" from archived data, clearly labelled as replay).

## 9. Proposed architecture (high level)
Eight layers per prompt §5: ingestion → processing → feature extraction → fusion (concatenation baseline first) → prediction engine → FastAPI backend → React/Leaflet/Plotly frontend → monitoring/deployment. Storage: PostgreSQL+PostGIS (metadata, predictions, audit), object/file store for rasters (Zarr/NetCDF/GeoTIFF), Redis+Celery for async, MLflow for tracking. Repo layout as in prompt §9. Detail deferred to Phase 3.

## 10. Technical feasibility
- Feasible on CPU: tabular/sequence models (GRU/LSTM track + intensity on best-track + ERA5 features), small CNN on cropped IR.
- Needs GPU/time: ConvLSTM, ViT, YOLO/U-Net training. Data limitation: NIO has few storms (order of tens of storms/decade [R: count from IBTrACS in Phase 2]) → small-data regime; strong event-based splits, transfer learning, ensembles, and honest wide uncertainty needed.
- Pixel-level eye/centre annotations likely unavailable → use best-track centres as weak labels for heatmap regression; eye segmentation likely dropped or self-supervised (Tier C).
- RI in NIO: very few positive events → likely cannot claim validated skill; report as exploratory with Brier/reliability and CIs.
- Overall verdict: Tier A feasible; Tier B partially; Tier C data-gated.

## 11. Risks and mitigations
| Risk | Mitigation |
|---|---|
| MOSDAC access delays/denied | start access request now; fallback ladder; replay mode |
| Small NIO sample, overfit | event/season split, ensembles, transfer from other basins as pretraining (data only, not product scope) |
| Label inconsistency across agencies | store agency-native values + conventions; no silent conversion |
| Temporal leakage | split by storm, then season; leakage tests in CI |
| Overclaiming skill | no numbers reported unless computed; "Not yet evaluated" template |
| Misuse as warning | disclaimer, "experimental" badges, no evacuation/surge claims |
| Scope creep | tier gating, approval gates per phase |
| Licence/ToS violation | per-source licence register; no scraping outside terms |
| Compute limits | CPU-first baselines; GPU optional |

## 12. Measurable acceptance criteria (Phase 1 exit + project-level)
Phase 1 exit: this document approved; assumptions/open-question registers accepted; scope + bbox frozen; tier assignment accepted.
Project-level (targets set only after baselines exist; these are *process* criteria now): 100% of API outputs carry model-version, data-version, timestamps, uncertainty field; 0 storm overlap across train/val/test (automated test); every connector has documented schema/auth/limits/retry; ablation of 5 required configurations executed and reported honestly; every dashboard forecast view shows the disclaimer; stale-data flag triggers when latency exceeds configured threshold. Numeric skill targets (MAE, track error) deliberately not set until a persistence/CLIPER-style baseline is measured.

## 13. Initial roadmap
P1 Requirements (now) → P2 Literature + source verification (confirm all [R] items) → P3 Design → P4 Connectors (IBTrACS + ERA5 first, then IMERG, then MOSDAC) → P5 Preprocessing → P6 Dataset engineering → P7 Baselines (track/intensity GRU first) → P8 Evaluation + ablations → P9 Backend → P10 Frontend → P11 Real-time pipeline → P12 Testing → P13 Deployment → P14 Docs. Approval gate after each phase. Suggested early action in parallel: request MOSDAC access.

## 14. Assumptions register
A1 Python/PyTorch/FastAPI/React default stack accepted. A2 CPU dev machine (macOS), GPU optional/cloud later. A3 Bbox 0–30N, 40–100E. A4 Single primary developer. A5 IBTrACS IMD fields suffice as primary labels. A6 ERA5/NWP used for environment; ERA5 not real-time. A7 IMD categories use 3-min-mean wind thresholds in knots (17–27 D, 28–33 DD, 34–47 CS, 48–63 SCS, 64–89 VSCS, 90–119 ESCS, ≥120 Super CS) — **[R] confirm against IMD documentation in Phase 2**. A8 RI definition provisional (e.g. ≥30 kt/24 h) — fix in Phase 2 with NIO literature. A9 Research prototype, no public hosting at v1.

## 15. Open questions register
Q1 Confirm bbox (include Andaman Sea / Gulf of Aden?). Q2 Do you already have MOSDAC credentials/approval? Q3 Available compute (GPU? cloud budget?). Q4 Deliverable context (course project, thesis, paper)? Affects documentation depth and deadline. Q5 Real-time latency expectations vs replay-mode acceptability. Q6 Single user or multi-user deployment? Q7 Preferred RI threshold and whether to include it in v1. Q8 Is time-bounded (deadline) — drives tier cut.

## Deliverable checklist
[ ] Problem statement [ ] Objectives/tiers [ ] Scope [ ] FR/NFR [ ] Stakeholders [ ] Use cases [ ] Source feasibility [ ] Architecture overview [ ] Feasibility [ ] Risks [ ] Acceptance criteria [ ] Roadmap [ ] Assumptions [ ] Open questions
## Validation checklist
No fabricated URLs/DOIs/results; every external claim tagged V/A/R; no code written; scope matches prompt; disclaimer text included.

## Project Progress Register
- Completed phases: Phase 1 draft (pending approval)
- Implemented modules: none
- Tested modules: none
- Known issues: none
- Dataset availability: to verify in Phase 2 and Phase 4
- Model versions: none
- Next: on approval, begin Phase 2 (literature review + source verification)

## Verification of this plan
Execution after approval is documentation-only: create `docs/phase1-requirements.md` from this content; check file exists and all 15 sections present; grep for `[R]` items and confirm each maps to a Phase 2 task. No code or tests run in Phase 1.
