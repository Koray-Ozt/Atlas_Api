"""Integration tests run the real app against a real MongoDB (see docker-compose.yml)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import Settings
from app.main import create_app


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(mongo_db=f"atlas_test_{uuid.uuid4().hex[:8]}")


@pytest.fixture(scope="session")
def sync_db(settings):
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")  # fails loudly if MongoDB is not running
    yield client[settings.mongo_db]
    client.drop_database(settings.mongo_db)
    client.close()


@pytest.fixture(scope="session")
def client(settings, sync_db):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _empty_orders(sync_db):
    sync_db.orders.delete_many({})
