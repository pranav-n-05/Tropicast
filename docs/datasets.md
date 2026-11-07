# Dataset documentation

All datasets are rebuilt deterministically by `tropicast ingest`, `train` and `satellite`.
`data_version = sha256(raw IBTrACS ‖ domain+training config)[:12]` and is recorded in
`data/processed/dataset_manifest.json`.

## D1. Tidy tracks (`data/processed/tracks.pkl`)
One row per storm × observation time, with exactly one agency per row.

| column | units | notes |
|---|---|---|
| sid, season, name, subbasin | – | IBTrACS identifiers; subbasin BB/AS/MM |
| time | UTC | 3-hourly for RSMC New Delhi |
| lat, lon | deg | agency position (New Delhi preferred, else USA, else WMO/merged) |
| wind_kt | kt | agency maximum sustained wind; **never converted** |
| wind_avg_min | min | 3 (newdelhi), 1 (usa) |
| pres_hpa | hPa | agency central pressure |
| agency | – | newdelhi / usa / none |
| native_grade, ci_number | – | IMD grade string, Dvorak CI |
| dist2land_km, landfall_km | km | IBTrACS distance to land (0 = over land) |
| is_provisional | bool | IBTrACS provisional track |

QC drop counts are in `reports/data_quality.json`.

## D2. Forecast samples (built in memory by `datasets/samples.py`)
- **Sample:** one storm × issue time t0 with wind ≥ 17 kt (IMD depression), RSMC New Delhi rows only.
- **Input window:** 24 h of history (four 6 h motion and intensity-change vectors). Shorter histories are padded and
  flagged with `hist_len`.
- **Leads:** 6, 12, 24, 48, 72 h. Targets are `dx`/`dy` (km), `dw` (kt), and `lat`/`lon` for verification. A target
  is NaN when there is no observation at t0+L.
- **Environment:** SHIPS t=0 predictors joined backward within 3 h (never a later analysis); `env_missing` flag.
- **Splits (season, event-disjoint, asserted):** train 1982–2012, validation 2013–2018, test 2019–2025. Training uses
  every 3-hourly issue; validation and test use synoptic issues only.
- **Seed:** 42 (`configs/training.yaml`).
- **Class balance (RI ≥ 30 kt / 24 h):** about 5–7 % positive per split; exact counts are in `reports/evaluation.md`.

## D3. Environment (`data/processed/env.pkl`)
2,199 SHIPS IO cases (1990–2021) matched to 154 IMD storms by exact time and nearest position (≤ 150 km; median
offset about 45 km, reflecting JTWC vs IMD fixes). Predictors and units are in `src/tropicast/ingestion/ships.py`.

## D4. Satellite set (`data/processed/satset.{npz,pkl}`)
- HURSAT-B1 v06 IRWIN brightness temperature (K). For each 3-hourly time, the satellite with the lowest view-zenith
  angle (VZA ≤ 65°) is kept.
- Central 160 px (about 11°) block-averaged to 80 × 80 (about 15.5 km pixels). Images with more than 5 % missing
  pixels are dropped; remaining gaps are median-filled.
- Joined to RSMC New Delhi labels at the exact time: 3,447 images from 172 storms, 1982–2015. Images at t−6 h and
  t−12 h are attached when available.
- **CV folds (season blocks):** 1982–95, 1996–2001, 2002–06, 2007–11, 2012–15.
- **Known limitations:** pre-1998 images come mostly from GMS at the disk edge (high VZA); the satellite mix changes
  over time (MET-5/7 IODC, FY-2, MTSAT); best-track intensities are themselves satellite-derived estimates.

## D5. Boundaries
Natural Earth 1:10m admin-1 (public domain), clipped to the domain and simplified at 0.02°
(`data/processed/coast_admin1.geojson`).
