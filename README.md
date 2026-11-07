# Tropicast

**Research decision-support prototype for tropical cyclones in the North Indian Ocean (Bay of Bengal + Arabian Sea).**
It tracks storms, classifies them on the IMD scale, and issues *experimental* track and intensity forecasts with
calibrated uncertainty, out to 72 hours.

> This platform provides experimental AI-based decision support. It is not an official weather warning, evacuation
> advisory, or disaster-management product. For safety-critical decisions, follow official advisories from the India
> Meteorological Department and relevant disaster-management authorities.

## What works today (v0.1)

| Capability | Status |
|---|---|
| IBTrACS v04r01 NI ingestion (conditional GET, sha256, provenance manifest) | working |
| QC + agency-explicit tidy tracks (RSMC New Delhi 3-min preferred, JTWC 1-min flagged, **no silent conversion**) | working |
| IMD classification (D … SuCS) + category probabilities | working |
| Track forecasts 6/12/24/48/72 h: persistence, ridge, GBM, GRU deep ensemble | working, evaluated |
| Intensity forecasts with 90 % intervals | working, evaluated |
| Split-conformal uncertainty (track cones 67/90 %, wind intervals) | working, coverage reported |
| Rapid-intensification probability | experimental. **No demonstrated skill on validation** (shown in the UI) |
| FastAPI service, audit log, rate limit, source-status endpoint | working |
| Dashboard (map, cones, hindcast slider with verification, intensity chart, evaluation, data status) | working |
| Real-time-capable pipeline (polls, detects active storms, stores forecasts, labels freshness honestly) | working; latency limited by IBTrACS (days) |
| Satellite imagery (MOSDAC/INSAT, Himawari), ERA5, IMERG | **not available**: credentials required; connectors are explicit scaffolds |
| Detection / eye segmentation / Grad-CAM / multimodal fusion | **not yet evaluated**: needs imagery |

## Quick start

```bash
uv venv -p 3.12 .venv && uv pip install -e ".[dev]"   # or: python -m venv .venv && pip install -e ".[dev]"
.venv/bin/tropicast ingest        # download IBTrACS NI (~28 MB), build processed tables + QC report
.venv/bin/tropicast train         # train, calibrate, evaluate, register (~3 min on a laptop CPU)
.venv/bin/tropicast pipeline --once   # one real-time cycle: fetch, find active storms, forecast, store
.venv/bin/tropicast serve         # http://127.0.0.1:8000  (dashboard)  /docs  (OpenAPI)
.venv/bin/python -m pytest -q     # 55 tests
```

Docker: `docker compose up --build`. On first start the `api` container ingests the data and trains the models.
The `pipeline` worker starts once `api` reports healthy, then runs a cycle every `PIPELINE_INTERVAL_MIN`.

## Results

The training pipeline writes all numbers to [reports/evaluation.md](reports/evaluation.md). None are typed in by hand.
The test set is the 2019–2025 seasons, unseen storms. Models are selected on 2013–2018 data and trained on 1982–2012.
The latest run selected `gru_ensemble+pr`, a GRU deep ensemble that predicts the correction to persistence:

| lead | track error km (persistence) | skill vs persistence | wind MAE kt (persistence) |
|---|---|---|---|
| 24 h | 144 (155) | +7 % | 10.0 (12.5) |
| 48 h | 293 (344) | +15 % | 16.5 (20.5) |
| 72 h | 409 (531) | +23 % | 19.8 (24.5) |

At 6–12 h, persistence is as good as any learned model or slightly better. All learned models move storms too slowly
on the test seasons; see the along-track bias in the report. Use these numbers for research context only; they do not
indicate operational skill.

## Layout

```
configs/      domain (bbox), IMD categories, sources register, training config
src/tropicast/
  ingestion/  connector base (retry, conditional GET, checksum, manifest), IBTrACS, credential scaffolds
  preprocessing/ tidy agency-explicit tracks + QC
  geospatial/ great-circle, along/cross-track
  classification/ IMD scale
  datasets/   sample builder (no leakage), season split, versioned build
  models/     persistence, ridge, GBM, GRU ensemble, persistence-residual wrapper, conformal, RI
  training/   train → calibrate (val) → select (val) → evaluate (test) → register
  evaluation/ metrics + markdown report
  inference/  forecast product with uncertainty, provenance and warnings
  realtime/   pipeline + freshness
  database/   SQLite store: forecasts, pipeline runs, audit log
  api/        FastAPI app (+ serves frontend/)
frontend/     dashboard (Leaflet + Plotly, no build step)
docs/         requirements, architecture, data sources, model card, literature, roadmap
tests/        unit + integration + API tests
```

## Documentation
- [docs/phase1-requirements.md](docs/phase1-requirements.md): requirements, risks, assumptions
- [docs/architecture.md](docs/architecture.md): design, data flow, schemas, API
- [docs/data_sources.md](docs/data_sources.md): source register and access status
- [docs/model_card.md](docs/model_card.md): model inputs and outputs, limitations, uncertainty
- [docs/literature.md](docs/literature.md): methods references and research gaps
- [docs/roadmap.md](docs/roadmap.md): progress register and next steps

Data: IBTrACS (Knapp et al., 2010, *BAMS*, doi:10.1175/2009BAMS2755.1), NOAA NCEI.
The best track used for labels is from RSMC New Delhi (IMD).
