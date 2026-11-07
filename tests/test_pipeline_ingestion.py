from datetime import datetime, timezone

import pandas as pd
import pytest

from tropicast.ingestion.base import Connector
from tropicast.realtime.pipeline import active_storms, freshness


class _Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def iter_content(self, n):
        yield self._body


def test_conditional_download_and_manifest(tmp_path, monkeypatch):
    con = Connector({"name": "t"}, tmp_path)
    con.source_id = "t"
    calls = []

    def fake(method, url, headers=None, **kw):
        calls.append(headers or {})
        if "If-Modified-Since" in (headers or {}):
            return _Resp(304)
        return _Resp(200, b"a,b\n1,2\n", {"Last-Modified": "Thu, 05 Nov 2026 10:05:33 GMT"})

    monkeypatch.setattr(con, "_request", fake)
    dest = con.data_dir / "x.csv"
    r1 = con.download("http://example/x.csv", dest)
    assert r1.status == "ok" and r1.changed and dest.read_bytes() == b"a,b\n1,2\n" and len(r1.sha256) == 64
    r2 = con.download("http://example/x.csv", dest)
    assert r2.status == "not_modified" and not r2.changed
    assert calls[1]["If-Modified-Since"] == "Thu, 05 Nov 2026 10:05:33 GMT"
    st = con.status()
    assert st["last_attempt_status"] == "not_modified" and st["sha256"] == r1.sha256


def test_failed_source_is_recorded_not_raised(tmp_path, monkeypatch):
    from tropicast.ingestion.base import SourceUnavailableError
    con = Connector({"name": "t"}, tmp_path)

    def boom(*a, **k):
        raise SourceUnavailableError("down")

    monkeypatch.setattr(con, "_request", boom)
    r = con.download("http://example/x.csv", con.data_dir / "x.csv")
    assert r.status == "error" and "down" in r.error


@pytest.mark.parametrize("age_h,status", [(3, "real_time"), (100, "recent"), (200, "delayed"),
                                          (400, "stale"), (24 * 400, "archive")])
def test_freshness_labels(age_h, status):
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    last = pd.Timestamp(now) - pd.Timedelta(hours=age_h)
    assert freshness(last, now)["status"] == status


def test_old_file_never_produces_active_storms():
    t = pd.DataFrame({"sid": ["a", "a"], "time": pd.to_datetime(["2001-01-01", "2001-01-02"], utc=True)})
    assert active_storms(t, now=datetime(2026, 11, 7, tzinfo=timezone.utc)).empty


def test_recent_storm_is_active():
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    t = pd.DataFrame({"sid": ["a", "b"],
                      "time": [pd.Timestamp(now) - pd.Timedelta(hours=10), pd.Timestamp(now) - pd.Timedelta(days=20)]})
    assert list(active_storms(t, now)["sid"]) == ["a"]


def test_notifications_deduplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("TROPICAST_DB", str(tmp_path / "n.sqlite"))
    from tropicast.database import store
    assert store.notify("new_system", "X active", "sid1", "new:sid1") is True
    assert store.notify("new_system", "X active", "sid1", "new:sid1") is False
    assert [n["kind"] for n in store.notifications()] == ["new_system"]
