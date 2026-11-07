# API reference (v1)

Generated from the FastAPI OpenAPI schema (`docs/openapi.json`; interactive docs at `/docs`).
Every data response includes `disclaimer`; forecast-type responses include `product`, model versions and `data_version`.

| method | path | summary | parameters |
|---|---|---|---|
| GET | `/api/v1/health` | Health |  |
| GET | `/api/v1/sources` | Sources |  |
| GET | `/api/v1/storms` | Storms | `season_from`, `season_to`, `q`, `min_wind`, `limit` |
| GET | `/api/v1/storms/{sid}` | Storm | `sid`* |
| GET | `/api/v1/storms/{sid}/forecast` | Storm Forecast | `sid`*, `issue_time` |
| GET | `/api/v1/storms/{sid}/satellite` | Storm Satellite | `sid`*, `time` |
| GET | `/api/v1/storms/{sid}/exposure` | Storm Exposure | `sid`*, `issue_time`, `members` |
| GET | `/api/v1/evaluation/{name}` | Evaluation Extra | `name`* |
| GET | `/api/v1/active` | Active |  |
| GET | `/api/v1/models` | Models |  |
| GET | `/api/v1/evaluation` | Evaluation |  |
| GET | `/api/v1/pipeline/runs` | Runs | `limit` |
| POST | `/api/v1/pipeline/run` | Trigger |  |
| GET | `/api/v1/notifications` | Notifications | `limit` |
| GET | `/api/v1/audit` | Audit | `limit` |
| GET | `/api/v1/config/categories` | Categories |  |

`*` = required. Errors: 404 unknown storm/report, 422 insufficient history or invalid issue time, 429 rate limit (120/min/IP), 503 data/models not built.

## Product types
| product | meaning |
|---|---|
| HISTORICAL_BEST_TRACK | observed best-track (archive) |
| PROVISIONAL_TRACK | recent provisional track; may be revised |
| EXPERIMENTAL_AI_FORECAST | model forecast or hindcast (`mode`), with calibrated uncertainty |
| EXPERIMENTAL_TRACK_EXPOSURE | landfall/strike probabilities from member tracks |
| RESEARCH_SATELLITE_ESTIMATE | CNN intensity from HURSAT IR (1982-2015) with Grad-CAM |
| ACTIVE_SYSTEMS | systems in the latest data window with freshness |
