"""
Integration test configuration.

Skips all integration tests if required infrastructure is not reachable,
rather than failing slowly with connection timeouts.
"""

import pytest
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

MONGO_URL = "mongodb://admin:password@localhost:27017/"
_PING_TIMEOUT_MS = 1000


def _mongo_is_reachable() -> bool:
    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=_PING_TIMEOUT_MS)
        client.admin.command("ping")
        client.close()
        return True
    except ServerSelectionTimeoutError:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_mongodb():
    """Skip the entire integration test session if MongoDB is not reachable."""
    if not _mongo_is_reachable():
        pytest.skip(
            "MongoDB not reachable at localhost:27017 — "
            "start it with: docker-compose up -d mongodb"
        )
