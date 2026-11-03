import pytest

from app.errors import InvalidTransitionError
from app.orders.domain import OrderStatus, compute_total, ensure_transition
from app.orders.schemas import OrderItem

P, PD, S, C = (
    OrderStatus.PENDING,
    OrderStatus.PAID,
    OrderStatus.SHIPPED,
    OrderStatus.CANCELLED,
)


@pytest.mark.parametrize("current,new", [(P, PD), (P, C), (PD, S), (PD, C)])
def test_allowed_transitions(current, new):
    ensure_transition(current, new)


@pytest.mark.parametrize("current,new", [(P, S), (P, P), (PD, P), (S, C), (S, PD), (C, P), (C, PD)])
def test_forbidden_transitions(current, new):
    with pytest.raises(InvalidTransitionError):
        ensure_transition(current, new)


def test_compute_total_sums_line_items_in_cents():
    items = [
        OrderItem(sku="A", quantity=2, unit_price_cents=1999),
        OrderItem(sku="B", quantity=1, unit_price_cents=501),
    ]
    assert compute_total(items) == 4499
