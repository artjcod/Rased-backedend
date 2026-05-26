"""
Connexion à MongoDB et initialisation de Beanie.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from .config import settings
from .models import ALL_MODELS

_client: AsyncIOMotorClient | None = None


async def init_db():
    """À appeler au démarrage de l'app (lifespan)."""
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(database=_client[settings.mongo_db_name], document_models=ALL_MODELS)


async def close_db():
    """À appeler à l'arrêt de l'app."""
    global _client
    if _client:
        _client.close()
        _client = None
