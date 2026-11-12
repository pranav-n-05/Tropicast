"""API tests against the real processed data / trained models (skipped if absent)."""
import pytest
from fastapi.testclient import TestClient

from tropicast import config
from tropicast.datasets.build import processed_dir

pytestmark = pytest.mark.skipif(
    not (processed_dir() / "dataset_manifest.json").exists() or not (config.artifacts_dir() / "registry.json").exists(),
    reason="run `tropicast ingest` and `tropicast train` first")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["TROPICAST_DB"] = str(tmp_path_factory.mktemp("db") / "t.sqlite")
    from tropicast.api.app import app
    return TestClient(app)


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_storm_list_has_disclaimer(client):
    r = client.get("/api/v1/storms", params={"q": "AMPHAN"}).json()
    assert "not an official" in r["disclaimer"].lower()
    assert r["data"][0]["peak_category"] == "SuCS"


def test_hindcast_has_uncertainty_versions_and_verification(client):
    sid = client.get("/api/v1/storms", params={"q": "AMPHAN"}).json()["data"][0]["sid"]
    f = client.get(f"/api/v1/storms/{sid}/forecast", params={"issue_time": "2020-05-17T12:00:00Z"}).json()
    assert f["product"] == "EXPERIMENTAL_AI_FORECAST" and f["mode"] == "hindcast"
    for lead in f["leads"]:
        assert lead["track_radius_km_90"] >= lead["track_radius_km_67"] > 0
        assert lead["wind_kt_90"][0] <= lead["wind_kt"] <= lead["wind_kt_90"][1]
    assert f["model"]["track"] and f["model"]["data_version"]
    assert len(f["verification"]) == 5


def test_unknown_storm_404(client):
    assert client.get("/api/v1/storms/NOPE/forecast").status_code == 404


def test_bad_issue_time_422(client):
    sid = client.get("/api/v1/storms", params={"q": "AMPHAN"}).json()["data"][0]["sid"]
    assert client.get(f"/api/v1/storms/{sid}/forecast", params={"issue_time": "1999-01-01T00:00Z"}).status_code == 422


def test_audit_log_records_requests(client):
    rows = client.get("/api/v1/audit").json()
    assert rows and {"endpoint", "model_version", "status"} <= rows[0].keys()


def test_sources_report_credentials_honestly(client):
    d = client.get("/api/v1/sources").json()["data"]
    assert d["mosdac_insat"]["status"] == "requires_credentials"
    assert d["ibtracs_ni"]["status"] == "implemented"


def test_satellite_product_at_requested_time(client):
    r = client.get("/api/v1/storms/2007314N10093/satellite", params={"time": "2007-11-14T12:00:00Z"})
    if r.status_code == 503:
        pytest.skip("satellite CNN not trained")
    p = r.json()
    assert r.status_code == 200 and p["time"].startswith("2007-11-14")
    assert p["cnn_wind_kt_90"][0] <= p["cnn_wind_kt"] <= p["cnn_wind_kt_90"][1]
    assert len(p["gradcam"]) == 64 and p["product"] == "RESEARCH_SATELLITE_ESTIMATE"


def test_exposure_endpoint(client):
    p = client.get("/api/v1/storms/2020136N10088/exposure",
                   params={"issue_time": "2020-05-18T12:00:00Z", "members": 100}).json()
    assert 0 <= p["p_landfall_72h"] <= 1 and p["product"] == "EXPERIMENTAL_TRACK_EXPOSURE"
    assert all(0 <= r["probability"] <= 1 for r in p["strike_probability"])
