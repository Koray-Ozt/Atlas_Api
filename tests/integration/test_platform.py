def test_health_checks_the_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_the_error_envelope(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_request_id_is_generated_and_echoed(client):
    generated = client.get("/health").headers["X-Request-ID"]
    assert len(generated) == 32
    echoed = client.get("/health", headers={"X-Request-ID": "trace-42"})
    assert echoed.headers["X-Request-ID"] == "trace-42"


def test_indexes_are_created_on_startup(client, sync_db):
    assert {"customer_email_created_at", "status_created_at"} <= set(
        sync_db.orders.index_information()
    )
