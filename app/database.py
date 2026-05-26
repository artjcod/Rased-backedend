"""
Connexion à MongoDB et initialisation de Beanie.
Supporte MongoDB local et MongoDB Atlas (TLS/SSL requis).
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from .config import settings
from .models import ALL_MODELS

_client: AsyncIOMotorClient | None = None


async def init_db():
    """À appeler au démarrage de l'app (lifespan)."""
    global _client

    is_atlas = "mongodb.net" in settings.mongo_uri or "+srv" in settings.mongo_uri

    client_kwargs = {
        "serverSelectionTimeoutMS": 10000,   # 10s avant d'abandonner
        "connectTimeoutMS": 10000,
        "socketTimeoutMS": 30000,
    }

    # Atlas requiert TLS ; les options sont dans l'URI +srv, pas besoin de les
    # répéter, mais on force tlsAllowInvalidCertificates=False pour la sécurité.
    if is_atlas:
        client_kwargs["tls"] = True
        client_kwargs["tlsAllowInvalidCertificates"] = False

    _client = AsyncIOMotorClient(settings.mongo_uri, **client_kwargs)

    # Vérifier la connexion avant de continuer
    await _client.admin.command("ping")

    await init_beanie(
        database=_client[settings.mongo_db_name],
        document_models=ALL_MODELS,
    )


async def close_db():
    """À appeler à l'arrêt de l'app."""
    global _client
    if _client:
        _client.close()
        _client = None
