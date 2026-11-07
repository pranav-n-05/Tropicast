# Model card: Tropicast v0.2

**Status:** experimental research models. Not for operational use. Every number below comes from the reports listed
next to it; regenerate them with the CLI.

## M1. Track and intensity forecaster (`reports/evaluation.md`)
| item | value |
|---|---|
| Target | east/north displacement (km) and wind change (kt) at +6/12/24/48/72 h |
| Labels | RSMC New Delhi best track (IBTrACS v04r01), 3-min winds |
| Inputs | 24 h track/intensity history, position, pressure, context; SHIPS t=0 environment where available (1990–2021) |
| Spatial domain | 0–30°N, 40–100°E |
| Split | seasons: train 1982–2012, validation 2013–2018, test 2019–2025 (event-disjoint, asserted) |
| Candidates | persistence; ridge+pr; GBM; GBM+pr; GRU ensemble+pr; GBM+pr+env; GRU ensemble+pr+env ("+pr" = learns the correction to persistence) |
| Baseline | persistence (no-skill reference); skill = 1 − error/persistence error on the same samples |
| Ablation | track → +intensity → +context; env-only vs temporal vs temporal+env on the homogeneous 2019–2021 subset |
| Selection | lowest mean validation error over leads, separately for track and intensity; the test set is never used for choices |
| Uncertainty | split-conformal on validation storms: track radius (normalised by ensemble spread for the GRU), CQR or residual conformal for wind; coverage reported on test |
| Inference | `inference.forecast.forecast_storm` → API `/storms/{sid}/forecast` |

**Findings worth knowing**
- **Persistence at short leads:** at 6–12 h, persistence is as good as any learned model or slightly better.
  Learned models gain from 24 h onward.
- **Negative along-track bias:** the forecasts move storms too slowly, but this is the error-minimising answer.
  Scaling the validation forecasts by 0.9–1.3 showed that the unscaled forecast is already near-optimal. Mean track
  error at 72 h: 522 km (0.9), 514 km (1.0), 514 km (1.1), 520 km (1.2), 531 km (1.3). Under directional uncertainty,
  the expected-error-minimising median track is shorter than any single realised track. **Do not "correct" it by
  stretching.**
- **Environment:** environmental predictors reduce error on cases where they exist; see the environment ablation
  table.

## M2. Rapid-intensification classifier (experimental)
| item | value |
|---|---|
| Label | ΔV ≥ 30 kt in 24 h (IMD winds); Kotal & Roy Bhowmik (2013) convention; base rate about 5–7 % |
| Models | logistic and GBM, each with and without the SHIPS environment; no class re-weighting |
| Selection | lowest validation Brier score |
| Scores | Brier, BSS vs training climatology, ROC AUC, reliability (evaluation.md) |
| Status | the payload carries `brier_skill` per split; the UI says "NO demonstrated skill" when validation BSS ≤ 0 |

## M3. Satellite intensity CNN (`reports/satellite_evaluation.md`)
| item | value |
|---|---|
| Input | HURSAT-B1 IRWIN brightness temperature, 64×64 centre crop of 80×80 (about 15.5 km pixels) |
| Architecture | 4 conv blocks (16-32-48-64), global average pool, MLP → (mean, log-variance); Gaussian NLL |
| Augmentation | random rotation + ±4 px shift. **No mirroring**: it would reverse the Northern Hemisphere cyclonic spiral. |
| Training | AdamW, cosine learning rate, 15 epochs; deployable model = 3-member ensemble on all 1982–2015 images |
| Evaluation | nested 5-fold season-block CV (inner 2-fold out-of-fold predictions for stacking), so no test-label leakage |
| Uncertainty | 8-rotation test-time augmentation + ensemble variance; 90 % interval via normalised conformal factor from inner OOF residuals |
| Explainability | Grad-CAM on the last conv block: an interpretive aid, not causation |
| Limitations | best-track intensity is itself satellite-derived (label noise); satellite eras differ; archive ends 2015, so research only |

## M4. Fusion models (satellite study)
Concatenation of CNN outputs + IR structure features + environment + track history into GBM (absolute-error loss).
The configurations follow the prompt's §6 ablation (satellite-only, env-only, sat+env, sat+env+temporal, full). The
"full" estimation configuration includes the previous best-track wind (t−6 h). It answers "does imagery add value
beyond the last advisory?" and is compared against that reference directly.

## M5. Centre localisation (`reports/localization.json`)
DSNT-style heatmap network on 56×56 crops shifted up to ±10 px (about 155 km). The reference is the interpolated
best-track centre (a weak label). Baselines: crop centre, coldest cloud.

## M6. Landfall / strike probability (`reports/landfall_evaluation.json`)
Monte-Carlo member tracks drawn from calibrated 90 % radii (σ = r90/2.146), AR(1)-correlated across leads (ρ = 0.85),
interpolated hourly and intersected with Natural Earth admin-1 regions. Verified on 12-hourly test issues
(2019–2025) with Brier, BSS, AUC and reliability. Centre-based only: not wind, surge, rain or evacuation guidance.

## Versioning
`<model>-<data_version>-<config_sha>-<UTC>` is stored in `artifacts/registry.json` and in every payload. The
satellite CNN is stored in `artifacts/satellite_cnn.pt` with its training-set metadata.
