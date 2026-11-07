"""Source registry: maps ``configs/sources.yaml`` entries to connector classes."""
from __future__ import annotations

from pathlib import Path

from tropicast import config
from tropicast.ingestion.base import Connector
from tropicast.ingestion.hursat import HURSATConnector
from tropicast.ingestion.ibtracs import IBTrACSConnector
from tropicast.ingestion.ships import SHIPSConnector
from tropicast.ingestion.scaffolds import ERA5Connector, HimawariConnector, IMERGConnector, MOSDACConnector

_CLASSES: dict[str, type[Connector]] = {
    "ibtracs_ni": IBTrACSConnector,
    "hursat_b1": HURSATConnector,
    "ships_io": SHIPSConnector,
    "era5": ERA5Connector,
    "gpm_imerg": IMERGConnector,
    "mosdac_insat": MOSDACConnector,
    "himawari": HimawariConnector,
}


def get(key: str, data_dir: Path | None = None) -> Connector:
    cfg = config.load("sources")["sources"][key]
    return _CLASSES[key](cfg, data_dir or config.DATA_DIR)


def all_connectors(data_dir: Path | None = None) -> dict[str, Connector]:
    return {k: get(k, data_dir) for k in config.load("sources")["sources"] if k in _CLASSES}
