# Installation and operations guide

## Requirements
- Python 3.11–3.13, about 4 GB RAM, about 3 GB disk (raw downloads; processed imagery is about 50 MB)
- Internet access to ncei.noaa.gov, rammb-data.cira.colostate.edu and raw.githubusercontent.com (Natural Earth)
- Optional: Docker 24+; an NVIDIA GPU with a CUDA build of PyTorch

## Local install
```bash
git clone <repo> tropicast && cd tropicast
uv venv -p 3.12 .venv && uv pip install -e ".[dev]"       # or python -m venv + pip
.venv/bin/tropicast ingest          # IBTrACS + SHIPS -> data/processed (about 1 min)
.venv/bin/tropicast train           # track/intensity/RI models -> artifacts/, reports/evaluation.md (about 5 min)
.venv/bin/tropicast satellite       # HURSAT download (about 2.5 GB transfer, 20-30 min) + CNN study (CPU, about 1-2 h)
.venv/bin/tropicast risk-eval       # landfall verification (about 10 min)
.venv/bin/tropicast serve --host 0.0.0.0 --port 8000
.venv/bin/python -m pytest -q
```
Use `tropicast satellite --fast` for a quick smoke run, and `--skip-fetch` if the imagery is already downloaded.

## Docker
```bash
cp .env.example .env
docker compose up --build -d          # api on :8000, pipeline worker
docker compose logs -f api
```
On first start, the `api` container ingests data and trains the track models. The satellite study is not run
automatically because it is too heavy for a cold start. To run it inside the container:
`docker compose exec api tropicast satellite`.
Data, artifacts and reports live in named volumes (`tropicast-data`, `tropicast-artifacts`, `tropicast-reports`).

GPU: replace the base image with a CUDA PyTorch runtime and drop the CPU wheel index in the `Dockerfile`. The code
uses the CPU unless CUDA tensors are explicitly enabled; GPU acceleration has not been benchmarked.

## Configuration
| file | purpose |
|---|---|
| `configs/domain.yaml` | basin, bbox, subbasins, primary agency |
| `configs/sources.yaml` | source register (URLs, status, latency, stale thresholds) |
| `configs/imd_categories.yaml` | IMD thresholds and RI definition |
| `configs/training.yaml` | seeds, history, leads, splits, GRU hyperparameters |
| env `TROPICAST_DB`, `TROPICAST_DATA_DIR`, `TROPICAST_CONFIG_DIR`, `PIPELINE_INTERVAL_MIN` | runtime overrides |

## Monitoring
- `GET /api/v1/health`: data and model readiness (Docker healthcheck).
- `GET /api/v1/sources`: per-source last attempt, success time, remote age.
- `GET /api/v1/pipeline/runs`: cycle duration, status (`ok` or `partial`), per-storm errors.
- `GET /api/v1/audit`: every forecast request with model version, duration and status.
- Logs: structured stdout (`docker compose logs`).

## Backup and recovery
- **Back up:** `data/tropicast.sqlite` (forecasts, runs, audit), `artifacts/` (models and registry), `reports/`.
  Example: `sqlite3 data/tropicast.sqlite ".backup backup.sqlite"` and `tar czf artifacts.tgz artifacts reports`.
- **Restore:** put the files back and restart. Raw and processed data need no backup; `tropicast ingest` rebuilds them
  deterministically (checked by `data_version`).
- **Model rollback:** `artifacts/registry.json` points to one `run-*` directory. Point it at an older run directory
  and restart the API.

## Enabling credential-gated sources
| source | steps |
|---|---|
| ERA5 | Create a Copernicus CDS account and put the key in `~/.cdsapirc`; `pip install .[era5]`; implement `ERA5Connector.fetch` (scaffold) |
| IMERG | Earthdata login in `~/.netrc`; implement `IMERGConnector.fetch` |
| MOSDAC (INSAT-3D/3DR) | Register and request access; set `MOSDAC_USER` and `MOSDAC_PASSWORD`; implement `MOSDACConnector.fetch`; reuse `satellite/*` (same 80×80 IR pipeline) |
