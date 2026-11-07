# Phase 2: Literature review and research-gap analysis

Method: targeted web searches (2026-11-07) plus the methods this platform implements. Each entry is labelled
**[peer-reviewed]**, **[dataset/technical doc]**, **[preprint/abstract]** or **[non-peer-reviewed]**.
DOIs were confirmed from publisher pages or from reference lists of later peer-reviewed papers. Entries marked
*(verify)* still need a first-hand check. Performance numbers are quoted from the papers, which use different data,
splits and periods; **they are not comparable with each other or with Tropicast results.**

## 1. Data foundations
| Ref | Type | Relevance |
|---|---|---|
| Knapp, Kruk, Levinson, Diamond & Neumann (2010) IBTrACS, *BAMS* 91, 363–376, doi:10.1175/2009BAMS2755.1 | peer-reviewed | Track archive; our labels (RSMC New Delhi fields) |
| Knapp & Kossin (2007) New global tropical cyclone data set from ISCCP B1 geostationary satellite observations, *J. Appl. Remote Sens.* 1, 013505, doi:10.1117/1.2712816 | peer-reviewed | HURSAT-B1, our open IR imagery source (1978–2015) |
| DeMaria & Kaplan (1994) SHIPS for the Atlantic basin, *Wea. Forecasting* 9, 209–220, doi:10.1175/1520-0434(1994)009<0209:ASHIPS>2.0.CO;2 (DOI from a secondary reference list) | peer-reviewed | Origin of the SHIPS predictors we use for the environment |
| CIRA/RAMMB SHIPS developmental data and predictor file (2026) — rammb-data.cira.colostate.edu/ships/data/ | dataset/technical doc | Our IO environmental predictors, 1990–2021 |

## 2. Intensity estimation from satellite imagery
| Ref | Type | Notes |
|---|---|---|
| Dvorak (1975) *Mon. Wea. Rev.* 103, 420–430 *(verify DOI)* | peer-reviewed | Operational subjective method. IMD best track carries CI numbers. |
| Pradhan et al. (2018) Tropical cyclone intensity estimation using a deep CNN, *IEEE Trans. Image Process.* 27(2) *(verify DOI 10.1109/TIP.2017.2766358)* | peer-reviewed | CNN on IR. Template for our satellite-only CNN. |
| ConvLSTM-based TC intensity estimation and classification using satellite imagery over the North Indian Ocean, *PLOS ONE*, doi:10.1371/journal.pone.0330705 | peer-reviewed | NIO-specific spatiotemporal model. Authors warn that models transfer poorly across basins. |
| Tropical cyclone intensity estimations over the Indian Ocean using machine learning, arXiv:2107.05573 | preprint | Indian Ocean ML intensity estimation |
| Several INSAT-3D CNN studies (ResearchGate, IJCRT, IJSREM; e.g. capsule networks reporting 13.24 kt RMSE) | non-peer-reviewed | Show interest in INSAT-3D. Venues and protocols are unverified; numbers not used. |

## 3. Track forecasting with deep learning
| Ref | Type | Notes |
|---|---|---|
| Alemany, Beltran, Perez & Ganzfried (2019) RNN hurricane trajectories, *AAAI*, arXiv:1802.02548 | peer-reviewed | RNN on best-track sequences (Atlantic) |
| Kumar et al. (2021) Prediction of landfall intensity, location and time of a TC, *AAAI* 35 (cdn.aaai.org/ojs/17741) | peer-reviewed | Stacked LSTM for the NIO; claims improvement over the IMD model on recent cases |
| Pal, Bandyopadhyay & Bose (2024) hybrid CNN-LSTM NIO track prediction, AGU Fall Meeting abstract 2024AGUFM.A03...38D | abstract | 62 Bay of Bengal + 33 Arabian Sea disturbances, 2013–2023; IR imagery, lead times to 72 h |
| MT-CycloneNet, multi-task BiLSTM + attention (Springer, doi prefix 10.1007/s43538-026-00926-4) | peer-reviewed *(verify details)* | Joint track, intensity and landfall |
| Track-prediction comparisons in the NIO (LSTM vs GRU vs RNN; Academia/ResearchGate) | non-peer-reviewed | Conflicting conclusions on which architecture is best. This motivates our controlled comparison against a persistence baseline. |

## 4. Rapid intensification
| Ref | Type | Notes |
|---|---|---|
| Kaplan & DeMaria (2003) *Wea. Forecasting* 18(6), 1093–1108, doi:10.1175/1520-0434(2003)018<1093:LCORIT>2.0.CO;2 | peer-reviewed | RI defined as about the 95th percentile of 24 h intensity change (Atlantic). Basis of the 30 kt / 24 h convention. |
| Kotal & Roy Bhowmik (2013) Large-scale characteristics of rapidly intensifying TCs over the Bay of Bengal and an RI index, *MAUSAM* 64(1), 13–24, doi:10.54302/mausam.v64i1.651 | peer-reviewed | IMD's RI index for the Bay of Bengal (≥30 kt / 24 h); part of IMD's objective Cyclone Prediction System |
| Nekkali et al. (2024) Magnitudes of RI and destruction of TCs over the NIO, *Int. J. Climatol.*, doi:10.1002/joc.8372 | peer-reviewed | NIO RI climatology |
| SSS-informed calibrated ML for RI, *Environ. Res. Lett.*, doi:10.1088/1748-9326/adac7f | peer-reviewed | SHIPS-RII predictors plus sea-surface salinity. Bay of Bengal storms dominate the low-salinity cases. |
| Suresh et al. (2025) RI in the Bay of Bengal, energetics view, *JGR Atmospheres*, doi:10.1029/2025JD044489 | peer-reviewed | RI storms have warmer SST (2005–2023) |
| Role of ocean heat content in Bay of Bengal RI (ESSOAr preprints, e.g. doi:10.22541/essoar.175820395.54901604/v1) | preprint | RI most frequent when OHC > 100 kJ/cm² |

## 5. Uncertainty quantification and explainability
| Ref | Type | Used for |
|---|---|---|
| Lakshminarayanan, Pritzel & Blundell (2017) deep ensembles, *NeurIPS*, arXiv:1612.01474 | peer-reviewed | GRU and CNN ensembles |
| Vovk, Gammerman & Shafer (2005) *Algorithmic Learning in a Random World*, Springer | book | Split-conformal calibration |
| Romano, Patterson & Candès (2019) conformalized quantile regression, *NeurIPS*, arXiv:1905.03923 | peer-reviewed | Wind intervals |
| Selvaraju et al. (2017) Grad-CAM, *ICCV*, arXiv:1610.02391 | peer-reviewed | CNN saliency in the dashboard |

## 6. Comparison of approaches (qualitative)
| Approach | Inputs | Strength | Weakness for the NIO |
|---|---|---|---|
| Persistence / CLIPER | track history | robust, hard to beat at short leads | no recurvature or intensity skill |
| SHIPS-type statistical | environment + history | interpretable; operational pedigree | depends on analysis quality; linear |
| CNN on IR | satellite | captures inner-core structure | needs large labelled imagery; INSAT access is restricted |
| RNN/LSTM/GRU tracks | track sequence | learns nonlinear motion | small NIO sample (~400 storms) causes overfitting |
| ConvLSTM / CNN-LSTM | image sequences | spatiotemporal | most data-hungry; poor cross-basin transfer |

## 7. Research gaps and how Tropicast responds
| Gap | Evidence | Tropicast response |
|---|---|---|
| Few open, reproducible NIO baselines with event-disjoint splits and published code | Most NIO DL work found is non-peer-reviewed or lacks split details | Season-block splits with automated leakage assertion; code and reports regenerate every number |
| Uncertainty rarely calibrated or verified for NIO ML forecasts | Reviewed works report point errors | Conformal cones and intervals with per-lead coverage on unseen seasons |
| Modality value not isolated (does imagery or environment help?) | Studies use one fixed input set | §6 ablation: satellite-only, env-only, temporal, combined (reports/satellite_evaluation.md, reports/evaluation.md) |
| Agency wind conventions (IMD 3-min vs JTWC 1-min) mixed in ML labels | Common in public datasets | Agency carried on every row; no conversion; IMD category withheld for non-IMD winds |
| INSAT data access barrier | MOSDAC registration and approval | Open HURSAT-B1 substitute for research; MOSDAC connector ready for when access is granted |
| RI prediction in the NIO is rare and imbalanced | RI climatology papers | Proper scores (Brier, BSS, reliability); environment-aware RI shows positive validation skill; reported honestly |

## 8. Methodological limitations recognised from the literature
- Best-track intensities are themselves estimates (Dvorak-based). Label noise of about 10 kt limits the achievable MAE.
- Satellite-era changes (INSAT, Meteosat-IODC from 1998) are a source of non-stationarity.
- Reanalysis and analysis predictors are not forecasts. Using t=0 analysis is legitimate. Using future developmental
  values ("perfect prognosis") leaks information and is excluded.
