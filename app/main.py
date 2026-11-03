"""Application factory."""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.config import Settings, get_settings
from app.db import ORDER_INDEXES
from app.errors import DatabaseUnavailableError, error_response, register_error_handlers
from app.logging import configure_logging, request_id_var
from app.orders.repository import OrderRepository
from app.orders.router import router as orders_router

logger = logging.getLogger("atlas")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = AsyncMongoClient(
            settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=settings.mongo_timeout_ms
        )
        collection = client[settings.mongo_db]["orders"]
        await collection.create_indexes(ORDER_INDEXES)  # idempotent
        app.state.client = client
        app.state.orders = OrderRepository(collection)
        logger.info("started", extra={"database": settings.mongo_db})
        yield
        await client.close()

    app = FastAPI(
        title="Atlas API",
        version="0.1.0",
        description="A small orders REST API built with FastAPI and MongoDB.",
        lifespan=lifespan,
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            logger.exception("unhandled_error")
            response = error_response(500, "internal_error", "Internal server error")
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        request_id_var.reset(token)
        return response

    @app.get("/health", tags=["meta"], summary="Liveness and database check")
    async def health(request: Request) -> dict[str, str]:
        try:
            await request.app.state.client.admin.command("ping")
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Database is not reachable") from exc
        return {"status": "ok"}

    app.include_router(orders_router)
    return app
