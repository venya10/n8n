def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_root_has_useful_links_instead_of_a_bare_404(client):
    res = client.get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["health"] == "/health"
