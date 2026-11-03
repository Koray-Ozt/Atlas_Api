"""HTTP layer for /orders."""

from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Request, Response

from app.errors import (
    ConflictError,
    InvalidIdError,
    NotFoundError,
    OrderNotEditableError,
)
from app.orders.domain import OrderStatus, compute_total, ensure_transition
from app.orders.repository import OrderRepository
from app.orders.schemas import (
    ErrorResponse,
    OrderCreate,
    OrderFilters,
    OrderOut,
    OrderPage,
    OrderUpdate,
)

router = APIRouter(prefix="/orders", tags=["orders"])

_NOT_FOUND = {404: {"model": ErrorResponse}}


def get_repository(request: Request) -> OrderRepository:
    return request.app.state.orders


Repo = Annotated[OrderRepository, Depends(get_repository)]


def parse_object_id(order_id: str) -> ObjectId:
    if not ObjectId.is_valid(order_id):
        raise InvalidIdError(f"'{order_id}' is not a valid order id")
    return ObjectId(order_id)


async def _get_or_404(repo: OrderRepository, order_id: str) -> tuple[ObjectId, dict[str, Any]]:
    oid = parse_object_id(order_id)
    doc = await repo.get(oid)
    if doc is None:
        raise NotFoundError(f"Order '{order_id}' not found")
    return oid, doc


@router.post("", response_model=OrderOut, status_code=201, summary="Create an order")
async def create_order(body: OrderCreate, repo: Repo, response: Response) -> OrderOut:
    doc = await repo.create(body)
    response.headers["Location"] = f"/orders/{doc['_id']}"
    return OrderOut.from_doc(doc)


@router.get("", response_model=OrderPage, summary="List orders (filtered, paginated)")
async def list_orders(filters: Annotated[OrderFilters, Query()], repo: Repo) -> OrderPage:
    docs, total = await repo.search(filters)
    return OrderPage(
        items=[OrderOut.from_doc(d) for d in docs],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/{order_id}", response_model=OrderOut, responses=_NOT_FOUND, summary="Get an order")
async def get_order(order_id: str, repo: Repo) -> OrderOut:
    _, doc = await _get_or_404(repo, order_id)
    return OrderOut.from_doc(doc)


@router.patch(
    "/{order_id}",
    response_model=OrderOut,
    responses={**_NOT_FOUND, 409: {"model": ErrorResponse}},
    summary="Change an order's status or items",
)
async def update_order(order_id: str, body: OrderUpdate, repo: Repo) -> OrderOut:
    oid, doc = await _get_or_404(repo, order_id)
    current = OrderStatus(doc["status"])
    changes: dict[str, Any] = {}

    if body.items is not None:
        if current is not OrderStatus.PENDING:
            raise OrderNotEditableError("Items can only be changed while the order is pending")
        changes["items"] = [item.model_dump() for item in body.items]
        changes["total_cents"] = compute_total(body.items)
    if body.status is not None:
        ensure_transition(current, body.status)
        changes["status"] = body.status.value

    updated = await repo.update(oid, changes, expected_status=current.value)
    if updated is None:
        raise ConflictError("Order was changed or deleted concurrently; please retry")
    return OrderOut.from_doc(updated)


@router.delete("/{order_id}", status_code=204, responses=_NOT_FOUND, summary="Delete an order")
async def delete_order(order_id: str, repo: Repo) -> None:
    if not await repo.delete(parse_object_id(order_id)):
        raise NotFoundError(f"Order '{order_id}' not found")
