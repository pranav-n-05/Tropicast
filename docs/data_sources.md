# Data-source register

Status as of 2026-11-07. URLs marked "verified" were fetched successfully from this environment.
"Requires verification" means not checked first-hand.

## Implemented
### S1. IBTrACS v04r01, North Indian basin: tracks and labels
| Field | Value |
|---|---|
| Official URL | https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv (verified, HTTP 200) |
| Access / auth | HTTPS bulk download, conditional GET (`Last-Modified`); no auth |
| Format | CSV; row 2 = units |
| Spatial / temporal | point fixes; RSMC New Delhi 3-hourly (observed 00–21 UTC every 3 h) |
| Coverage | NI basin 1842–present; RSMC New Delhi winds 1982–2025 (405 storms); v1 bbox 0–30°N, 40–100°E |
| Update / latency | file `Last-Modified` 2026-11-05; provisional storms about 4 days behind real time |
| Variables | position, `NEWDELHI_WIND` (kt, 3-min), `NEWDELHI_PRES` (hPa), `NEWDELHI_GRADE`, `NEWDELHI_CI`, `USA_WIND` (kt, 1-min), `DIST2LAND` (km), `TRACK_TYPE` |
| Quality / missing | provisional 2026 storms have only USA winds; pre-1982 storms have no New Delhi winds (excluded from training) |
| Licence | NOAA public data; cite Knapp et al. (2010) doi:10.1175/2009BAMS2755.1 |

### S2. SHIPS developmental database, Indian Ocean: environment
| Field | Value |
|---|---|
| Official URL | https://rammb-data.cira.colostate.edu/ships/data/IO/lsdiagi_1990_2021_5day.txt (verified, 38.6 MB); documentation …/ships_predictor_file_2026.pdf |
| Access / auth | HTTPS download; no auth |
| Format | fixed-width text; 23 lead columns (−12 to +120 h) per predictor; HEAD/TYPE/HIST lines |
| Spatial / temporal | area averages around the JTWC best-track centre (for example 200–800 km); 6-hourly |
| Coverage | IO cases 1990–2021 (3,412 cases); 2,199 matched to IMD storms (≤ 150 km, same time) |
| Latency | static developmental file (not real-time) |
| Variables used (t=0 only) | SHRD/SHDC shear (kt), SHTD heading, RHLO/RHMD/RHHI (%), RSST/CSST (°C), COHC (kJ cm⁻²), VMPI (kt), D200, Z850 (s⁻¹×10⁷), U200, EPOS, TWAC |
| Quality / missing | predictors missing unless TYPE 1 or 2; t>0 columns are perfect-prognosis along the verifying track (excluded) |
| Licence | public research data; cite DeMaria & Kaplan (1994) and the SHIPS predictor file |

### S3. HURSAT-B1 v06: IR imagery
| Field | Value |
|---|---|
| Official URL | https://www.ncei.noaa.gov/data/hurricane-satellite-hursat-b1/archive/v06/ (verified; per-year directories, files named by IBTrACS SID) |
| Access / auth | HTTPS tar.gz per storm; no auth |
| Format | netCDF per image, 301×301, 0.07° Mercator, storm-centred; IRWIN, IRWVP, VSCHN etc.; ARCHER and ODT diagnostics |
| Coverage | global 1978–2015; 191 IMD-labelled NI storms available, 174 processed; 3,447 labelled images after the VZA ≤ 65° filter |
| Latency | archive ends 2015, so satellite products are research/hindcast only |
| Quality | satellite mix changes over time (GMS edge-of-disk pre-1998, Meteosat-5/7 IODC 1998+, FY-2, MTSAT); HDF read errors on a few files resolved by re-download |
| Licence | NOAA public data; cite Knapp & Kossin (2007) doi:10.1117/1.2712816 |

### S4. Natural Earth 1:10m admin-1: coastal regions
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
(verified). Public domain. Clipped to the domain and simplified at 0.02°.

## Credential-gated (scaffold connectors)
| Source | Needed for | Access | Status / fallback |
|---|---|---|---|
| ISRO MOSDAC INSAT-3D/3DR | real-time imagery | registration + approval | requires_credentials; HURSAT used for research |
| Copernicus ERA5 | high-resolution environment | CDS key | requires_credentials; SHIPS used instead. PSL OPeNDAP (NCEP R1/OISST) returned HTTP 429 on 2026-11-07 |
| NASA GPM IMERG | rainfall footprint | Earthdata login | requires_credentials; rainfall objective blocked |
| Himawari-8/9 | supplementary imagery | public mirrors (requires verification); NI only at the disk edge | not implemented |
| NOAA OISST via CoastWatch ERDDAP | SST | public (verified working) | not needed: SHIPS RSST is used |
