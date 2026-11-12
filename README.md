# Tropicast

**Research decision-support platform for tropical cyclones in the North Indian Ocean (Bay of Bengal + Arabian Sea).**
It tracks storms, classifies them on the IMD scale, issues *experimental* 6–72 h track and intensity forecasts with
calibrated uncertainty, estimates intensity from satellite IR with Grad-CAM explanations, and estimates landfall
and coastal exposure. Every number it reports was produced by its own code on unseen storm seasons.

> This platform provides experimental AI-based decision support. It is not an official weather warning, evacuation
> advisory, or disaster-management product. For safety-critical decisions, follow official advisories from the India
> Meteorological Department and relevant disaster-management authorities.

## Capabilities (v0.2)
| Area | What is there |
|---|---|
| Data | IBTrACS v04r01 (RSMC New Delhi labels), SHIPS IO environment (t=0 only), HURSAT-B1 IR imagery, Natural Earth regions. Conditional GET, sha256, provenance manifests, QC report |
| Agency safety | IMD 3-min and JTWC 1-min winds kept separate, never converted; IMD category withheld for non-IMD winds |
| Track/intensity forecast | persistence, ridge, GBM, GRU deep ensemble, each with and without environment; persistence-residual learning; season-disjoint splits |
| Uncertainty | split-conformal 67/90 % cones and 90 % wind intervals; coverage verified on test seasons |
| Rapid intensification | environment-aware logistic model with proper scores; skill status shown in the UI |
| Satellite | IR CNN (rotation-only augmentation, TTA, ensemble), IR structure features, nested-CV multimodal ablation, stage classification, Grad-CAM |
| Centre localisation | heatmap (soft-argmax) network vs coldest-cloud and prior baselines |
| Coastal exposure | landfall and strike probabilities per state/province from member tracks; verified |
| Platform | FastAPI (16 endpoints, audit log, rate limit, notifications + webhook), dashboard, real-time pipeline with honest freshness, Docker |
| Not available | ERA5, IMERG rainfall, INSAT via MOSDAC (credentials); wind-field, surge or evacuation products (out of scope by design) |

## Results (test data = unseen seasons; full tables in `reports/`)
**Track and intensity, 2019–2025 storms.** Selected model: `gru_ensemble+pr`.
| lead | track error km (persistence) | skill | wind MAE kt (persistence) |
|---|---|---|---|
| 24 h | 144 (155) | +7 % | 10.0 (12.5) |
| 48 h | 293 (344) | +15 % | 16.5 (20.5) |
| 72 h | 409 (531) | +23 % | 19.8 (24.5) |

At 6–12 h, persistence is as good as any model or slightly better. The negative along-track bias is the
error-minimising shrinkage, checked by scaling forecasts on validation (see docs/model_card.md).

**Satellite study, nested season-block CV, 1982–2015, 3,447 images.**
| intensity estimation | MAE kt |
|---|---|
| climatology | 16.4 |
| CNN only | 11.4 |
| CNN + IR structure features | 9.9 |
| satellite + environment + track history (common subset) | 10.3 |
| + previous best-track wind, vs that wind alone | 3.8 vs 4.0 |

For the 24 h intensity change, the full multimodal model (12.0 kt) beats temporal-only (12.8) and persistence (15.0).

**Landfall probability (72 h, test seasons):** 309 issues, BSS +0.37, AUC 0.85. It over-forecasts at low
probabilities; see the reliability table.
**Centre localisation (2012–2015):** 72.5 km mean error vs 124 km (prior) and 176 km (coldest cloud); 36 km for
storms of 64 kt and above.
**RI:** environment-aware model has validation BSS +0.12 and AUC 0.80; test BSS +0.07.

## Quick start
```bash
uv venv -p 3.12 .venv && uv pip install -e ".[dev]"
.venv/bin/tropicast ingest       # IBTrACS + SHIPS → processed tables, QC report
.venv/bin/tropicast train        # forecast models + reports/evaluation.md (~5 min CPU)
.venv/bin/tropicast satellite    # HURSAT + CNN study + localisation + deploy CNN (~1–2 h CPU; --fast for a smoke run)
.venv/bin/tropicast risk-eval    # landfall verification
.venv/bin/tropicast serve        # http://127.0.0.1:8000 (dashboard), /docs (OpenAPI)
.venv/bin/python -m pytest -q    # 71 tests
```
Docker: `docker compose up --build`. The image was built and smoke-tested (`tropicast:0.2`).

## Documentation
| doc | content |
|---|---|
| [docs/final_report.md](docs/final_report.md) | generated final report (all metrics copied from reports/) |
| [docs/SRS.md](docs/SRS.md) | requirements with verification status |
| [docs/phase1-requirements.md](docs/phase1-requirements.md) | problem, scope, risks, assumptions |
| [docs/literature.md](docs/literature.md) | literature review and research gaps (verified citations) |
| [docs/architecture.md](docs/architecture.md) | layers, DFD, UML, sequences, ER, wireframe, config schema |
| [docs/data_sources.md](docs/data_sources.md), [docs/datasets.md](docs/datasets.md) | source register, dataset cards |
| [docs/model_card.md](docs/model_card.md) | models, uncertainty, limitations |
| [docs/api.md](docs/api.md), `docs/openapi.json` | API reference |
| [docs/user_manual.md](docs/user_manual.md), [docs/installation.md](docs/installation.md) | usage, install, operations, backup |
| [docs/testing_report.md](docs/testing_report.md) | test inventory and results |
| [docs/paper_outline.md](docs/paper_outline.md), [docs/roadmap.md](docs/roadmap.md) | paper plan, progress register |

## Data credits
IBTrACS: Knapp et al. (2010), doi:10.1175/2009BAMS2755.1 (NOAA NCEI). HURSAT-B1: Knapp & Kossin (2007),
doi:10.1117/1.2712816. SHIPS developmental data: CIRA/RAMMB (DeMaria & Kaplan 1994). Natural Earth (public domain).
Labels are the RSMC New Delhi (IMD) best track.

Licence: MIT (see LICENSE).
