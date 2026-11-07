# User manual

> Tropicast is experimental research software. It is not an official warning. For safety decisions follow the India
> Meteorological Department (https://mausam.imd.gov.in/) and your disaster-management authority.

## Opening the dashboard
Run `tropicast serve` and open http://127.0.0.1:8000. The header shows API health. The amber banner is the
disclaimer, and it cannot be dismissed.

## Panels
**Left: tabs**
- **Active**: systems whose latest observation falls in the newest data window. The coloured pill shows freshness:
  `real time` (≤ 6 h), `recent` (≤ 7 days), `delayed`, `stale`, or `archive` (a historical record). IBTrACS updates
  arrive days late, so live storms usually show `recent`.
- **Explorer**: search storms by name or SID, season range and minimum peak wind. The pill shows the peak IMD
  category, computed from IMD winds only.
- **Models**: test-set verification for every model, the ablations, the satellite study, centre localisation and
  landfall verification. ★ marks the model selected on validation data.
- **Data**: source status (implemented, requires credentials, or not implemented), last check, remote update time.
  The button runs one pipeline cycle.

**Centre: map**
| symbol | meaning |
|---|---|
| solid line coloured by IMD category | best-track observations |
| dashed line | provisional track (recent, may change) |
| orange dotted line + dots | AI forecast median |
| orange translucent circles | 67 % track uncertainty at each lead |
| white hollow circles | where the storm actually was (hindcast verification) |
| dashed blue rectangle | v1 domain |

**Right: storm detail**
1. **Header**: product type, freshness, agencies with averaging period, data version.
2. **Intensity chart**: observed wind, AI median, 90 % band, IMD thresholds (dotted), and the issue time (blue).
3. **Experimental forecast**: drag the *issue* slider to replay a forecast from any past synoptic time. For archived
   storms the default is the last issue that has 72 h of verification. The table shows position, 67/90 % radii,
   wind with 90 % interval, IMD category, and the error against the observed position (hindcast only). Below it:
   24 h category probabilities, rapid-intensification probability with climatology and skill status, and full
   provenance (model versions, uncertainty method, inputs used).
4. **Coastal exposure**: P(landfall within 72 h), likely landfall regions (state, province or division), landfall
   timing, and the probability that the centre passes within 100 km of each region. These are centre-track
   probabilities, *not* wind, surge or rain warnings.
5. **Satellite IR (research)**: for 1982–2015 storms with HURSAT imagery. Shows the enhanced-IR image, an optional
   Grad-CAM overlay, the CNN intensity estimate with 90 % interval versus best track, eye contrast, cold-cloud
   fraction and the ARCHER eye probability. Grad-CAM shows where the network looked; it is not a physical
   explanation.

## Warnings you may see
- *Input winds are from agency 'usa' (1-min)*: recent provisional storms only have JTWC winds. The intensity is not
  on the IMD scale, so the IMD category and RI probability are withheld.
- *Short track history*: the storm has less than 24 h of history, so uncertainty may be underestimated.
- *Environment unavailable*: SHIPS data covers 1990–2021. Outside that range the model behaves like the track-only
  model.

## Reading uncertainty
- A 67 % circle means that, in the past, about two out of three verifying positions fell inside circles of that size.
  Coverage on unseen seasons is listed in the Models tab.
- Wider circles are not a malfunction; they reflect genuine predictability limits.

## API quick reference
See [api.md](api.md). Example:
`curl "http://127.0.0.1:8000/api/v1/storms/2020136N10088/forecast?issue_time=2020-05-18T12:00:00Z"`
