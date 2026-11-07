"""Connector base class: retry, conditional download, checksums, provenance manifest."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)


class CredentialsRequiredError(RuntimeError):
    """Source needs credentials that are not configured."""


class SourceUnavailableError(RuntimeError):
    """Source could not be reached after retries."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


@dataclass
class FetchResult:
    """Provenance record for one fetch attempt."""

    source_id: str
    path: str | None
    url: str | None
    fetched_at: str
    changed: bool
    sha256: str | None = None
    bytes: int | None = None
    remote_last_modified: str | None = None
    status: str = "ok"            # ok | not_modified | error | credentials_required
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Connector:
    """Base class for all source connectors.

    Subclasses set ``source_id`` and implement :meth:`fetch`. Each fetch writes a
    JSON manifest next to the data so provenance survives restarts.
    """

    source_id: str = "base"
    max_retries: int = 4
    backoff_s: float = 2.0
    timeout_s: float = 120.0

    def __init__(self, cfg: dict[str, Any], data_dir: Path):
        self.cfg = cfg
        self.data_dir = data_dir / "raw" / self.source_id
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.json"

    def read_manifest(self) -> dict[str, Any] | None:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return None

    def write_manifest(self, result: FetchResult) -> None:
        prev = self.read_manifest() or {}
        history = prev.get("history", [])[-49:]
        history.append(asdict(result))
        latest_ok = asdict(result) if result.status in ("ok", "not_modified") else prev.get("latest_ok")
        if result.status == "not_modified" and prev.get("latest_ok"):
            latest_ok = {**prev["latest_ok"], "checked_at": result.fetched_at}
        self.manifest_path.write_text(
            json.dumps({"source_id": self.source_id, "latest": asdict(result),
                        "latest_ok": latest_ok, "history": history}, indent=2)
        )

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = requests.request(method, url, timeout=self.timeout_s, **kw)
                if r.status_code == 429 or r.status_code >= 500:
                    raise SourceUnavailableError(f"HTTP {r.status_code}")
                return r
            except (requests.RequestException, SourceUnavailableError) as exc:
                last = exc
                wait = self.backoff_s * (2 ** attempt)
                log.warning("%s: %s %s failed (%s); retry in %.1fs", self.source_id, method, url, exc, wait)
                time.sleep(wait)
        raise SourceUnavailableError(f"{self.source_id}: {url} unreachable: {last}")

    def download(self, url: str, dest: Path) -> FetchResult:
        """Conditional download (If-Modified-Since). Atomic write + checksum."""
        now = utcnow().isoformat()
        headers = {"User-Agent": "tropicast-research-prototype/0.1"}
        prev = (self.read_manifest() or {}).get("latest_ok")
        if prev and dest.exists() and prev.get("remote_last_modified"):
            headers["If-Modified-Since"] = prev["remote_last_modified"]
        try:
            r = self._request("GET", url, headers=headers, stream=True)
        except SourceUnavailableError as exc:
            res = FetchResult(self.source_id, str(dest) if dest.exists() else None, url, now, False,
                              status="error", error=str(exc))
            self.write_manifest(res)
            return res
        if r.status_code == 304:
            res = FetchResult(self.source_id, str(dest), url, now, False, sha256=prev.get("sha256"),
                              bytes=prev.get("bytes"), remote_last_modified=prev.get("remote_last_modified"),
                              status="not_modified")
            self.write_manifest(res)
            return res
        if r.status_code != 200:
            res = FetchResult(self.source_id, str(dest) if dest.exists() else None, url, now, False,
                              status="error", error=f"HTTP {r.status_code}")
            self.write_manifest(res)
            return res
        tmp = dest.with_suffix(dest.suffix + ".part")
        with tmp.open("wb") as fh:
            for block in r.iter_content(1 << 20):
                fh.write(block)
        digest = sha256_file(tmp)
        changed = not dest.exists() or (prev or {}).get("sha256") != digest
        tmp.replace(dest)
        res = FetchResult(self.source_id, str(dest), url, now, changed, sha256=digest,
                          bytes=dest.stat().st_size, remote_last_modified=r.headers.get("Last-Modified"))
        self.write_manifest(res)
        return res

    def fetch(self) -> FetchResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        """Freshness summary used by the API and dashboard."""
        m = self.read_manifest() or {}
        ok = m.get("latest_ok") or {}
        latest = m.get("latest") or {}
        out: dict[str, Any] = {
            "source_id": self.source_id,
            "name": self.cfg.get("name"),
            "implementation_status": self.cfg.get("status"),
            "last_attempt_at": latest.get("fetched_at"),
            "last_attempt_status": latest.get("status"),
            "last_success_at": ok.get("checked_at") or ok.get("fetched_at"),
            "remote_last_modified": ok.get("remote_last_modified"),
            "sha256": ok.get("sha256"),
        }
        lm = ok.get("remote_last_modified")
        if lm:
            age_h = (utcnow() - parsedate_to_datetime(lm)).total_seconds() / 3600
            out["remote_age_hours"] = round(age_h, 1)
        return out
