def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "ST CORE"
    assert data["version"] == "1.0.0"
    assert "database" in data
