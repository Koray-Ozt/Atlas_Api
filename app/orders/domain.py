"""Order business rules. Pure functions, no I/O."""

from collections.abc import Iterable
from enum import StrEnum
from typing import TYPE_CHECKING

from app.errors import InvalidTransitionError

if TYPE_CHECKING:
    from app.orders.schemas import OrderItem


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: set(),
    OrderStatus.CANCELLED: set(),
}


def ensure_transition(current: OrderStatus, new: OrderStatus) -> None:
    if new not in _TRANSITIONS[current]:
        raise InvalidTransitionError(f"Cannot change status from '{current}' to '{new}'")


def compute_total(items: "Iterable[OrderItem]") -> int:
    """Order total in cents. Money is kept as integers to avoid float rounding errors."""
    return sum(item.quantity * item.unit_price_cents for item in items)
