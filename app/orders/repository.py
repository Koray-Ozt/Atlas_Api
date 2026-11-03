"""All MongoDB access for orders lives here."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection

from app.orders.domain import OrderStatus, compute_total
from app.orders.schemas import OrderCreate, OrderFilters

LIST_SORT = [("created_at", DESCENDING), ("_id", DESCENDING)]


def build_filter(filters: OrderFilters) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if filters.status:
        query["status"] = filters.status.value
    if filters.customer_email:
        query["customer_email"] = filters.customer_email.lower()
    if filters.created_from or filters.created_to:
        window: dict[str, datetime] = {}
        if filters.created_from:
            window["$gte"] = filters.created_from
        if filters.created_to:
            window["$lte"] = filters.created_to
        query["created_at"] = window
    if filters.min_total_cents is not None:
        query["total_cents"] = {"$gte": filters.min_total_cents}
    return query


def _now() -> datetime:
    """Current UTC time truncated to milliseconds, the precision MongoDB stores."""
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


class OrderRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._col = collection

    async def create(self, data: OrderCreate) -> dict[str, Any]:
        now = _now()
        doc: dict[str, Any] = {
            "customer_email": data.customer_email,
            "items": [item.model_dump() for item in data.items],
            "status": OrderStatus.PENDING.value,
            "total_cents": compute_total(data.items),
            "created_at": now,
            "updated_at": now,
        }
        await self._col.insert_one(doc)  # adds "_id" to doc
        return doc

    async def get(self, order_id: ObjectId) -> dict[str, Any] | None:
        return await self._col.find_one({"_id": order_id})

    async def search(self, filters: OrderFilters) -> tuple[list[dict[str, Any]], int]:
        query = build_filter(filters)
        cursor = self._col.find(query).sort(LIST_SORT).skip(filters.offset).limit(filters.limit)
        docs = await cursor.to_list()
        total = await self._col.count_documents(query)
        return docs, total

    async def update(
        self, order_id: ObjectId, changes: dict[str, Any], expected_status: str
    ) -> dict[str, Any] | None:
        """Apply `changes` only if the order still has `expected_status` (optimistic check)."""
        return await self._col.find_one_and_update(
            {"_id": order_id, "status": expected_status},
            {"$set": {**changes, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete(self, order_id: ObjectId) -> bool:
        result = await self._col.delete_one({"_id": order_id})
        return result.deleted_count == 1
