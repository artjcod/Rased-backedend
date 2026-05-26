# ── Stage 1 : dépendances ────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# Dépendances système minimales (openpyxl a besoin de rien de spécial,
# motor/beanie utilisent les bindings async de pymongo qui sont en pur Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ── Stage 2 : image finale ───────────────────────────────────────────────────
FROM python:3.12-slim AS final

# Utilisateur non-root pour la sécurité
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copier les paquets installés depuis le stage deps
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copier le code source
COPY app/ ./app/

# Créer un répertoire pour les uploads temporaires
RUN mkdir -p /app/uploads && chown appuser:appgroup /app/uploads

USER appuser

# Variables d'environnement par défaut (surchargées par docker-compose / .env)
ENV MONGO_URI=mongodb://mongo:27017 \
    MONGO_DB_NAME=rased \
    CORS_ORIGINS=* \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Health check intégré à Docker (optionnel mais utile)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
