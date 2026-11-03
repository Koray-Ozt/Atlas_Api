"""Request and response models."""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.orders.domain import OrderStatus

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class OrderItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=1_000)
    unit_price_cents: int = Field(gt=0, le=100_000_000)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    items: list[OrderItem] = Field(min_length=1, max_length=50)

    @field_validator("customer_email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.lower()


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus | None = None
    items: list[OrderItem] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def _require_a_change(self) -> Self:
        if self.status is None and self.items is None:
            raise ValueError("Provide at least one of: status, items")
        return self


class OrderOut(BaseModel):
    id: str
    customer_email: str
    items: list[OrderItem]
    status: OrderStatus
    total_cents: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Self:
        return cls(id=str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"})


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int


class OrderFilters(BaseModel):
    """Query parameters of GET /orders."""

    status: OrderStatus | None = None
    customer_email: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_total_cents: int | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must not be later than created_to")
        return self


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
