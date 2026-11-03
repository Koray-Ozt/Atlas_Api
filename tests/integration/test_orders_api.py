import pytest


def payload(email="ada@example.com", items=None):
    items = items or [{"sku": "SKU-1", "quantity": 2, "unit_price_cents": 1500}]
    return {"customer_email": email, "items": items}


def create(client, **kwargs):
    response = client.post("/orders", json=payload(**kwargs))
    assert response.status_code == 201, response.text
    return response.json()


# --- create ---------------------------------------------------------------


def test_create_returns_201_with_computed_total_and_location(client):
    response = client.post("/orders", json=payload(email="Ada@Example.com"))
    body = response.json()
    assert response.status_code == 201
    assert response.headers["Location"] == f"/orders/{body['id']}"
    assert body["customer_email"] == "ada@example.com"
    assert body["status"] == "pending"
    assert body["total_cents"] == 3000


def test_create_rejects_invalid_payload_with_error_envelope(client):
    response = client.post("/orders", json={"customer_email": "nope", "items": []})
    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    assert {d["field"] for d in error["details"]} >= {"body.customer_email", "body.items"}


def test_create_rejects_client_supplied_total(client):
    response = client.post("/orders", json={**payload(), "total_cents": 1})
    assert response.status_code == 422


# --- read -----------------------------------------------------------------


def test_get_returns_the_order(client):
    created = create(client)
    response = client.get(f"/orders/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_order_returns_404(client):
    response = client.get("/orders/64b7f0f0f0f0f0f0f0f0f0f0")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_malformed_id_returns_422(client):
    response = client.get("/orders/not-an-id")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_id"


# --- list: filtering and pagination --------------------------------------


def test_list_paginates_newest_first(client):
    ids = [create(client)["id"] for _ in range(5)]
    page = client.get("/orders", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 5
    assert (page["limit"], page["offset"]) == (2, 2)
    assert [o["id"] for o in page["items"]] == [ids[2], ids[1]]


def test_list_filters_by_status_and_customer(client):
    paid = create(client, email="ada@example.com")
    create(client, email="ada@example.com")
    create(client, email="bob@example.com")
    client.patch(f"/orders/{paid['id']}", json={"status": "paid"})

    by_status = client.get("/orders", params={"status": "paid"}).json()
    assert [o["id"] for o in by_status["items"]] == [paid["id"]]

    by_customer = client.get("/orders", params={"customer_email": "BOB@example.com"}).json()
    assert by_customer["total"] == 1


def test_list_filters_by_minimum_total_and_dates(client):
    create(client, items=[{"sku": "A", "quantity": 1, "unit_price_cents": 1000}])
    create(client, items=[{"sku": "B", "quantity": 1, "unit_price_cents": 5000}])

    big = client.get("/orders", params={"min_total_cents": 2000}).json()
    assert big["total"] == 1 and big["items"][0]["total_cents"] == 5000

    assert (
        client.get("/orders", params={"created_from": "2999-01-01T00:00:00"}).json()["total"] == 0
    )
    assert client.get("/orders", params={"created_to": "2999-01-01T00:00:00"}).json()["total"] == 2


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1000}, {"status": "bogus"}])
def test_list_rejects_invalid_query_params(client, params):
    assert client.get("/orders", params=params).status_code == 422


# --- update ---------------------------------------------------------------


def test_status_follows_the_allowed_lifecycle(client):
    order_id = create(client)["id"]
    for new_status in ("paid", "shipped"):
        response = client.patch(f"/orders/{order_id}", json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["status"] == new_status


def test_invalid_status_transition_returns_409(client):
    order_id = create(client)["id"]
    response = client.patch(f"/orders/{order_id}", json={"status": "shipped"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


def test_items_can_change_only_while_pending(client):
    order_id = create(client)["id"]
    new_items = [{"sku": "NEW", "quantity": 3, "unit_price_cents": 100}]

    edited = client.patch(f"/orders/{order_id}", json={"items": new_items})
    assert edited.status_code == 200
    assert edited.json()["total_cents"] == 300

    client.patch(f"/orders/{order_id}", json={"status": "paid"})
    locked = client.patch(f"/orders/{order_id}", json={"items": new_items})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "order_not_editable"


def test_empty_patch_is_rejected(client):
    order_id = create(client)["id"]
    assert client.patch(f"/orders/{order_id}", json={}).status_code == 422


def test_patch_unknown_order_returns_404(client):
    response = client.patch("/orders/64b7f0f0f0f0f0f0f0f0f0f0", json={"status": "paid"})
    assert response.status_code == 404


# --- delete ---------------------------------------------------------------


def test_delete_removes_the_order(client):
    order_id = create(client)["id"]
    assert client.delete(f"/orders/{order_id}").status_code == 204
    assert client.get(f"/orders/{order_id}").status_code == 404
    assert client.delete(f"/orders/{order_id}").status_code == 404
