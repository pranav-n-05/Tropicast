# Architecture (Phase 3: system design, as built in v0.2)

## 1. Layered view
```mermaid
flowchart LR
  subgraph L1[1 Ingestion]
    IB[IBTrACS NI CSV<br/>conditional GET, sha256]
    SH[SHIPS IO lsdiag<br/>t=0 predictors]
    HU[HURSAT-B1 v06<br/>storm-centred IR]
    NE[Natural Earth admin-1]
    SC[ERA5 / IMERG / MOSDAC<br/>scaffolds: credentials_required]
  end
  subgraph L2[2 Processing]
    QC[QC + agency-explicit tidy tracks]
    EM[SHIPS↔IMD matching<br/>time + 150 km]
    IMG[VZA selection, crop, 80x80]
  end
  subgraph L3[3 Features]
    TF[track/intensity history]
    EF[environment t=0, backward as-of]
    IRF[IR ring/eye/asymmetry features]
    CF[CNN embedding + estimate]
  end
  subgraph L4[4 Fusion]
    FU[feature concatenation → GBM<br/>persistence-residual wrappers]
  end
  subgraph L5[5 Prediction engine]
    TR[track: persistence/ridge/GBM/GRU-ens]
    IN[intensity + RI]
    SAT[satellite CNN + Grad-CAM]
    LOC[centre heatmap net]
    RISK[landfall / strike Monte-Carlo]
    CAL[split-conformal calibration]
  end
  subgraph L6[6 Backend]
    API[FastAPI /api/v1] --- DB[(SQLite: forecasts,<br/>runs, audit)]
    REG[(artifacts/registry.json)]
  end
  subgraph L7[7 Frontend]
    UI[Leaflet + Plotly + canvas IR]
  end
  subgraph L8[8 Ops]
    RT[pipeline loop] --- DK[Docker compose<br/>healthchecks]
  end
  IB --> QC --> TF
  SH --> EM --> EF
  HU --> IMG --> IRF & CF
  TF & EF & IRF & CF --> FU --> TR & IN
  IMG --> SAT & LOC
  TR --> CAL --> RISK
  NE --> RISK
  TR & IN & SAT & RISK --> REG --> API --> UI
  RT --> IB & API
```

## 2. Data-flow diagram (level 1)
```mermaid
flowchart TB
  NOAA[(NOAA NCEI)] -->|IBTrACS CSV| P1[1.0 Ingest & QC]
  CIRA[(CIRA RAMMB)] -->|SHIPS lsdiag| P1
  NOAA -->|HURSAT tar.gz| P2[2.0 Image processing]
  P1 -->|tidy tracks, env| D1[(processed/*.pkl)]
  P2 -->|satset.npz| D1
  D1 --> P3[3.0 Train / calibrate / evaluate]
  P3 -->|models| D2[(artifacts)]
  P3 -->|metrics| D3[(reports)]
  D1 & D2 --> P4[4.0 Inference]
  P4 -->|forecast payloads| D4[(SQLite)]
  P4 --> P5[5.0 API]
  D3 & D4 --> P5
  P5 -->|JSON| USER((Researcher / analyst))
```

## 3. UML: main classes
```mermaid
classDiagram
  class Connector {+source_id; +fetch() FetchResult; +download(url,dest); +status() dict; -_request()}
  Connector <|-- IBTrACSConnector
  Connector <|-- SHIPSConnector
  Connector <|-- HURSATConnector
  Connector <|-- _CredentialScaffold
  _CredentialScaffold <|-- ERA5Connector
  _CredentialScaffold <|-- IMERGConnector
  _CredentialScaffold <|-- MOSDACConnector
  class SampleSet {+frame; +seq; +leads; +subset(mask); +target_cols(kind)}
  class Forecaster {<<protocol>> +fit(train,val); +predict(s) Prediction}
  Forecaster <|.. PersistenceModel
  Forecaster <|.. RidgeModel
  Forecaster <|.. GBMModel
  Forecaster <|.. GRUEnsemble
  Forecaster <|.. PersistenceResidual
  PersistenceResidual o-- Forecaster : base
  class ConformalCalibrator {+fit(val,pred); +track_radius(pred,q); +wind_interval(pred,q)}
  class RIModel {+fit(train); +predict_proba(s)}
  class CNNEstimator {+fit(bt,y); +predict(bt) ; +gradcam(bt)}
  class CentreNet
  class SatSet {+frame; +images; +prev6; +prev12}
```

## 4. Sequence: forecast request
```mermaid
sequenceDiagram
  participant U as Browser
  participant A as FastAPI
  participant I as inference.forecast
  participant R as registry (cached)
  participant L as risk.landfall
  participant S as SQLite
  U->>A: GET /storms/{sid}/forecast?issue_time
  A->>I: forecast_storm(track, t0, env)
  I->>R: load models + calibrators (lru_cache)
  I->>I: build_samples (history ≤ t0 only) → predict → conformal radii
  I-->>A: payload (medians, cones, intervals, versions, warnings)
  A->>A: attach verification if hindcast, freshness
  A->>S: audit row
  A-->>U: JSON
  U->>A: GET /storms/{sid}/exposure
  A->>L: exposure(forecast, n=300)
  L-->>A: P(landfall), regions, strike probabilities
  A-->>U: JSON
```

## 5. Sequence: real-time cycle
```mermaid
sequenceDiagram
  participant P as pipeline.run_once
  participant C as connectors
  participant B as datasets.build
  participant F as forecast
  participant S as SQLite
  P->>C: fetch IBTrACS (If-Modified-Since); status of others
  C-->>P: ok / not_modified / error (recorded, never raised)
  P->>B: build_processed() (cached by raw sha + config hash)
  P->>P: active_storms(): last obs ≤ 72 h of newest data AND not ancient
  loop each active storm
    P->>F: forecast_storm(track, env)
    F-->>P: payload or error (isolated)
    P->>S: save_forecast(+freshness)
  end
  P->>S: record_run(duration, ok|partial, details)
```

## 6. Database (SQLite; schema portable to PostgreSQL/PostGIS)
```mermaid
erDiagram
  forecasts { int id PK; text sid; text issue_time; text processed_at; text track_model; text intensity_model; text data_version; text source; json payload }
  pipeline_runs { int id PK; text started_at; text finished_at; real duration_s; text status; json details }
  audit_log { int id PK; text at; text endpoint; text sid; text issue_time; text model_version; text data_version; real duration_ms; text status; text error }
```
Constraint: `UNIQUE(sid, issue_time, track_model)` on forecasts makes re-runs idempotent.

## 7. Dashboard wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ◎ Tropicast   Bay of Bengal · Arabian Sea                              [API ok v0.2] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ EXPERIMENTAL. Not an official warning … follow IMD …                    IMD site ↗   │
├───────────────┬───────────────────────────────────────┬──────────────────────────────┤
│[Active|Explor-│                                       │ NAME  SID   [BEST TRACK][arch]│
│ er|Models|Data│        Leaflet map (dark)             │ observed / agencies / version │
│               │   — best track (IMD colours)          │ ┌ intensity chart ──────────┐ │
│ search …      │   - - provisional                     │ │ obs ─  AI ···  90% band   │ │
│ 1990–2026 ≥34 │   ··· AI median   ◯ 67% cones         │ └───────────────────────────┘ │
│ ▸ AMPHAN SuCS │   ○ verifying positions               │ issue ◀──────●──▶ 18 May 12Z │
│ ▸ FANI   ESCS │                                       │ lead pos r67/90 wind[90%] IMD │
│ …             │ ┌legend──────────┐                    │ category probs · P(RI) · prov.│
│               │ │ D DD CS SCS …  │                    │ Coastal exposure: P(lf), bars │
│               │ └────────────────┘                    │ Satellite IR + Grad-CAM, CNN  │
└───────────────┴───────────────────────────────────────┴──────────────────────────────┘
```

## 8. Configuration schema
| file | keys |
|---|---|
| domain.yaml | `basin`, `bbox{lat_min,lat_max,lon_min,lon_max}`, `subbasins[]`, `primary_agency`, `synoptic_hours[]` |
| sources.yaml | `sources.<id>{name,status,url,url_verified,auth,format,temporal_resolution,licence,expected_latency_hours,stale_after_hours,notes}` |
| imd_categories.yaml | `agency`, `wind_averaging_minutes`, `categories[{code,name,min_kt,max_kt}]`, `rapid_intensification{threshold_kt,window_h}` |
| training.yaml | `seed`, `timestep_h`, `history_steps`, `lead_times_h[]`, `min_wind_kt`, `split{train,val,test}`, `quantiles[]`, `gru{…}` |

## 9. Error handling, security and versioning
- **Errors:** connector retries with exponential backoff on network errors, 429 and 5xx; the failure is recorded in
  the manifest and the last good file is kept. The pipeline isolates failures per source and per storm (`partial`
  status). The API returns 404/422/503 with a message and writes an audit row.
- **Security:** read-only public data; no user accounts; per-IP rate limit; allow-listed report names; all API
  strings HTML-escaped in the UI; secrets only via environment or credential files (never committed); the container
  runs as a non-root user.
- **Data versioning:** `data_version` (raw sha + config hash), dataset manifest, per-source manifests.
- **Model versioning:** `<model>-<data_version>-<config_sha>-<UTC>` stored in the registry and in every payload.
  Rollback = repoint `registry.json`.

## 10. Deliberate deviations from the master prompt
| prompt default | v0.2 choice | reason |
|---|---|---|
| React | vanilla JS + Leaflet + Plotly (no build) | zero toolchain, served by the API; can be ported |
| PostgreSQL/PostGIS | SQLite | single file; spatial work is done in Python/shapely; schema portable |
| Celery/Redis | in-process loop + FastAPI background tasks | sources update on the scale of hours to days |
| MLflow | JSON registry + generated reports | one place to add MLflow logging (`training/pipeline.py`) |
| ERA5 | SHIPS developmental predictors | no CDS key; SHIPS is the operational predictor set |
| INSAT-3D/3DR | HURSAT-B1 | MOSDAC access pending; HURSAT is public and SID-keyed |
| attention / cross-attention fusion | concatenation (baseline) | the prompt asks for the baseline first; about 3.4k images is too few to justify more |
