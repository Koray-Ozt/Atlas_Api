import pytest
from pydantic import ValidationError

from app.orders.repository import build_filter
from app.orders.schemas import OrderCreate, OrderFilters, OrderUpdate

ITEM = {"sku": "SKU-1", "quantity": 1, "unit_price_cents": 100}


def test_create_normalizes_email_to_lowercase():
    order = OrderCreate(customer_email="Ada@Example.COM", items=[ITEM])
    assert order.customer_email == "ada@example.com"


@pytest.mark.parametrize(
    "payload",
    [
        {"customer_email": "not-an-email", "items": [ITEM]},
        {"customer_email": "a@example.com", "items": []},
        {"customer_email": "a@example.com", "items": [{**ITEM, "quantity": 0}]},
        {"customer_email": "a@example.com", "items": [{**ITEM, "unit_price_cents": -5}]},
        {"customer_email": "a@example.com", "items": [ITEM], "total_cents": 1},
    ],
)
def test_create_rejects_invalid_payloads(payload):
    with pytest.raises(ValidationError):
        OrderCreate(**payload)


def test_update_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        OrderUpdate()


def test_filters_reject_inverted_date_range():
    with pytest.raises(ValidationError):
        OrderFilters(created_from="2026-02-01T00:00:00", created_to="2026-01-01T00:00:00")


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_filters_bound_pagination(params):
    with pytest.raises(ValidationError):
        OrderFilters(**params)


def test_build_filter_is_empty_without_criteria():
    assert build_filter(OrderFilters()) == {}


def test_build_filter_combines_all_criteria():
    flt = OrderFilters(
        status="paid",
        customer_email="Ada@Example.com",
        created_from="2026-01-01T00:00:00",
        min_total_cents=500,
    )
    query = build_filter(flt)
    assert query["status"] == "paid"
    assert query["customer_email"] == "ada@example.com"
    assert set(query["created_at"]) == {"$gte"}
    assert query["total_cents"] == {"$gte": 500}
