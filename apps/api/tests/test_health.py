from fastapi.testclient import TestClient

from vrm_api.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "environment" in body
    assert "version" in body


def test_root_redirects_to_docs_info():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["docs"] == "/docs"
