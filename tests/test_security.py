"""Security-oriented tests: rate limiting, input allow-lists, no secrets in repo, safe rendering."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from tropicast.api import app as app_mod

ROOT = Path(__file__).resolve().parents[1]


def test_rate_limit_returns_429():
    app_mod._hits.clear()
    c = TestClient(app_mod.app)
    codes = [c.get("/api/v1/health").status_code for _ in range(app_mod.RATE_LIMIT + 3)]
    assert codes[:app_mod.RATE_LIMIT] == [200] * app_mod.RATE_LIMIT
    assert codes[-1] == 429
    app_mod._hits.clear()


def test_report_endpoint_allow_list_blocks_traversal():
    app_mod._hits.clear()
    c = TestClient(app_mod.app)
    for name in ("../../etc/passwd", "..%2F..%2Fconfigs", "registry"):
        assert c.get(f"/api/v1/evaluation/{name}").status_code == 404


def test_no_secrets_committed():
    pat = re.compile(r"(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|password\s*=\s*['\"][^'\"]+['\"])", re.I)
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "configs").glob("*.yaml")) + [ROOT / ".env.example"]:
        assert not pat.search(p.read_text()), f"possible secret in {p}"


def test_frontend_escapes_untrusted_strings():
    js = (ROOT / "frontend" / "app.js").read_text()
    assert "const esc =" in js
    # storm names / messages from the API must go through esc() before innerHTML
    assert "${esc(s.name)}" in js and "${esc(e.message)}" in js
