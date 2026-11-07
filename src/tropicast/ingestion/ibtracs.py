"""IBTrACS (NOAA NCEI) North Indian basin connector and raw parser."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tropicast.ingestion.base import Connector, FetchResult

RAW_FILENAME = "ibtracs.NI.list.v04r01.csv"

# Only columns used downstream are parsed; the rest stay in the raw file.
USECOLS = [
    "SID", "SEASON", "NUMBER", "BASIN", "SUBBASIN", "NAME", "ISO_TIME", "NATURE", "LAT", "LON",
    "WMO_WIND", "WMO_PRES", "WMO_AGENCY", "TRACK_TYPE", "DIST2LAND", "LANDFALL",
    "USA_LAT", "USA_LON", "USA_WIND", "USA_PRES", "USA_AGENCY",
    "NEWDELHI_LAT", "NEWDELHI_LON", "NEWDELHI_GRADE", "NEWDELHI_WIND", "NEWDELHI_PRES",
    "NEWDELHI_CI", "NEWDELHI_DP",
]


class IBTrACSConnector(Connector):
    """Downloads the IBTrACS NI CSV (conditional GET) and records provenance."""

    source_id = "ibtracs"

    @property
    def raw_path(self) -> Path:
        return self.data_dir / RAW_FILENAME

    def fetch(self) -> FetchResult:
        return self.download(self.cfg["url"], self.raw_path)


def read_raw(path: Path) -> pd.DataFrame:
    """Parse the IBTrACS CSV. Second header line holds units and is skipped.

    Blank cells are encoded as a single space in IBTrACS; they become NaN.
    """
    df = pd.read_csv(
        path, skiprows=[1], usecols=lambda c: c in USECOLS, low_memory=False,
        keep_default_na=False, na_values=[" ", ""],
    )
    missing = set(USECOLS) - set(df.columns)
    if missing:
        raise ValueError(f"IBTrACS schema changed; missing columns: {sorted(missing)}")
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], utc=True, errors="coerce")
    return df
