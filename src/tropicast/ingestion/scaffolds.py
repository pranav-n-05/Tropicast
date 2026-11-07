"""Connectors for sources that need credentials. SCAFFOLDS: not functional yet.

They exist so the registry, status endpoint and dashboard report these sources
honestly ("requires_credentials") instead of pretending data is present.
"""
from __future__ import annotations

import os
from pathlib import Path

from tropicast.ingestion.base import Connector, CredentialsRequiredError, FetchResult, utcnow


class _CredentialScaffold(Connector):
    credential_hint: str = ""

    def credentials_present(self) -> bool:  # pragma: no cover - environment dependent
        return False

    def fetch(self) -> FetchResult:
        res = FetchResult(self.source_id, None, None, utcnow().isoformat(), False,
                          status="credentials_required",
                          error=f"Not implemented / credentials required: {self.credential_hint}")
        self.write_manifest(res)
        return res

    def require(self) -> None:
        if not self.credentials_present():
            raise CredentialsRequiredError(self.credential_hint)


class ERA5Connector(_CredentialScaffold):
    """Copernicus CDS ERA5. Needs ~/.cdsapirc and ``pip install .[era5]``."""

    source_id = "era5"
    credential_hint = "Copernicus CDS API key in ~/.cdsapirc"

    def credentials_present(self) -> bool:
        return (Path.home() / ".cdsapirc").exists()


class IMERGConnector(_CredentialScaffold):
    """NASA GPM IMERG. Needs Earthdata login (~/.netrc)."""

    source_id = "gpm_imerg"
    credential_hint = "NASA Earthdata credentials in ~/.netrc"

    def credentials_present(self) -> bool:
        return (Path.home() / ".netrc").exists()


class MOSDACConnector(_CredentialScaffold):
    """ISRO MOSDAC INSAT-3D/3DR. Needs registration and approved access."""

    source_id = "mosdac_insat"
    credential_hint = "MOSDAC account (MOSDAC_USER / MOSDAC_PASSWORD) with approved data access"

    def credentials_present(self) -> bool:
        return bool(os.environ.get("MOSDAC_USER") and os.environ.get("MOSDAC_PASSWORD"))


class HimawariConnector(_CredentialScaffold):
    source_id = "himawari"
    credential_hint = "Not implemented; partial NIO coverage (requires verification)"
