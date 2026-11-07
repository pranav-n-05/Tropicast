import numpy as np
import pandas as pd

from tropicast.ingestion.ibtracs import USECOLS
from tropicast.preprocessing.tracks import build_tracks, to_synoptic


def _raw(rows):
    base = {c: np.nan for c in USECOLS}
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], utc=True)
    return df


def test_agency_preference_and_no_conversion():
    raw = _raw([
        dict(SID="A", SEASON=2020, SUBBASIN="BB", NAME="X", ISO_TIME="2020-05-01 00:00", LAT=10, LON=88,
             NEWDELHI_LAT=10.1, NEWDELHI_LON=88.1, NEWDELHI_WIND=45, USA_WIND=55, TRACK_TYPE="main"),
        dict(SID="A", SEASON=2020, SUBBASIN="BB", NAME="X", ISO_TIME="2020-05-01 03:00", LAT=10.2, LON=88,
             USA_LAT=10.3, USA_LON=88.2, USA_WIND=60, TRACK_TYPE="main"),
    ])
    t, qc = build_tracks(raw)
    assert list(t["agency"]) == ["newdelhi", "usa"]
    assert list(t["wind_kt"]) == [45, 60]          # USA wind kept as-is, not converted
    assert list(t["wind_avg_min"]) == [3.0, 1.0]
    assert t["lat"].iloc[0] == 10.1 and t["lat"].iloc[1] == 10.3


def test_qc_drops_outside_bbox_bad_time_and_spur():
    raw = _raw([
        dict(SID="A", SEASON=2020, SUBBASIN="BB", ISO_TIME="2020-05-01 00:00", LAT=10, LON=88, TRACK_TYPE="main"),
        dict(SID="B", SEASON=2020, SUBBASIN="BB", ISO_TIME="2020-05-01 00:00", LAT=10, LON=120, TRACK_TYPE="main"),
        dict(SID="C", SEASON=2020, SUBBASIN="BB", ISO_TIME=None, LAT=10, LON=88, TRACK_TYPE="main"),
        dict(SID="D", SEASON=2020, SUBBASIN="BB", ISO_TIME="2020-05-01 00:00", LAT=10, LON=88,
             TRACK_TYPE="spur-merge"),
    ])
    t, qc = build_tracks(raw)
    assert list(t["sid"]) == ["A"]
    assert qc.dropped["outside_bbox"] == 1 and qc.dropped["invalid_time"] == 1 and qc.dropped["spur_track"] == 1


def test_implausible_wind_set_nan_not_dropped():
    raw = _raw([dict(SID="A", SEASON=2020, SUBBASIN="AS", ISO_TIME="2020-05-01 00:00", LAT=15, LON=65,
                     NEWDELHI_WIND=400, TRACK_TYPE="main")])
    t, qc = build_tracks(raw)
    assert len(t) == 1 and np.isnan(t["wind_kt"].iloc[0])


def test_synoptic_filter(straight_storm):
    s = to_synoptic(straight_storm, [0, 6, 12, 18])
    assert set(s["time"].dt.hour) <= {0, 6, 12, 18}
    assert len(s) == len(straight_storm) // 2
