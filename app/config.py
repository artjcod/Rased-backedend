"""
Configuration centralisée. Lit les variables d'environnement (ou .env).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # URI de connexion MongoDB
    # Local : mongodb://localhost:27017
    # Atlas : mongodb+srv://user:pass@cluster.mongodb.net
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "rased"

    # CORS : domaine du frontend autorisé (en prod, mettre l'URL Netlify)
    cors_origins: str = "*"

    # Clés API pour le repli LLM (extraction de métadonnées).
    # Gemini est gratuit (niveau free de Google AI Studio) — recommandé pour démarrer.
    # Laisser vide = extraction par règles uniquement (aucun appel LLM).
    gemini_api_key: str = ""
    anthropic_api_key: str = ""


settings = Settings()
