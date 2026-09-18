"""
Motor (async MongoDB) client for the ML service.
Uses a module-level singleton so the connection is shared across all requests.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the 'mega' database handle."""
    client = get_client()
    # Extract DB name from URI, default to 'mega'
    db_name = settings.mongodb_uri.rsplit("/", 1)[-1].split("?")[0] or "mega"
    return client[db_name]
