# Rased — Backend (avec persistance MongoDB)

API de traitement d'extraits bancaires avec stockage persistant :
upload → détection de structure → normalisation → classification → **persistance MongoDB** → CRUD.

## Prérequis

- Python 3.10+
- MongoDB : soit local, soit un cluster gratuit [MongoDB Atlas](https://www.mongodb.com/atlas)

## Démarrage rapide

```bash
cd rased-backend
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # puis ajuster MONGO_URI si besoin
uvicorn app.main:app --reload --port 8000
```

Si tu n'as pas MongoDB en local, installe-le ou utilise Atlas (gratuit) et mets
l'URI dans `.env`. Pour MongoDB local rapide via Docker :

```bash
docker run -d -p 27017:27017 --name rased-mongo mongo:7
```

API : http://localhost:8000 · Documentation Swagger : http://localhost:8000/docs

## Architecture (ODM Beanie)

> MongoDB n'utilise pas d'ORM (réservé au SQL) mais un **ODM** (Object-Document Mapper).
> On utilise **Beanie**, basé sur Motor (driver async) + Pydantic.

```
app/
  config.py          → variables d'environnement
  database.py        → connexion Mongo + init Beanie (au démarrage)
  models.py          → documents : Company, Upload, Transaction
  main.py            → API + endpoints CRUD
  parser.py          → pipeline de lecture/normalisation
  aggregates.py      → calcul des agrégats (pur, testable)
  classifier.py      → classification hybride
  normalize.py       → dates, montants
  parsers/           → détection de schéma
```

## Endpoints

| Méthode | Route | Rôle |
|---------|-------|------|
| POST | `/api/upload` | importe et **persiste** un relevé + ses transactions |
| GET | `/api/uploads` | liste des relevés importés |
| GET | `/api/transactions` | liste des transactions (filtres : `upload_id`, `needs_review`) |
| GET | `/api/summary` | agrégats calculés depuis la base |
| PATCH | `/api/transactions/{id}` | **met à jour le label** (étiquetage manuel) |
| POST | `/api/transactions/{id}/reclassify` | **reclassifie** (auto, ou catégorie forcée) |
| DELETE | `/api/transactions/{id}` | **supprime** une transaction |
| DELETE | `/api/uploads/{id}` | supprime un relevé et toutes ses transactions |

## Modèle de données

- **Transaction** : date, description, amount (signé), balance, category,
  counterparty, confidence, needs_review, **manually_labeled** (traçabilité des
  corrections manuelles), upload_id (indexé).
- **Upload** : filename, mode détecté, confiance, nombre de transactions.

## Tests

```bash
python tests/test_parser.py        # parsing des 3 formats
python tests/test_aggregates.py    # logique d'agrégation
```

## Déploiement

Railway / Render / Fly.io :
- Variables : `MONGO_URI` (Atlas), `CORS_ORIGINS` (URL Netlify)
- Démarrage : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Prochaines étapes

1. **Auth & multi-tenant** : lier les uploads/transactions à `company_id` réel.
2. **LLM** : implémenter `app/llm_stub.py` pour les cas ambigus.
3. **Embeddings** : classification par similarité (recherche vectorielle Atlas).

## Repli LLM pour l'extraction de métadonnées (optionnel)

L'extraction de banque/compte/client se fait d'abord **par règles** (gratuit,
instantané). Si les règles échouent sur un relevé inhabituel, un LLM est appelé
**en repli** pour compléter. Deux fournisseurs supportés :

- **Gemini (gratuit, recommandé)** : obtenir une clé sur https://aistudio.google.com/apikey
  puis mettre `GEMINI_API_KEY=...` dans `.env`.
- **Claude (payant)** : `ANTHROPIC_API_KEY=...` dans `.env`.

Sans clé, le système fonctionne par règles uniquement (aucun coût, aucun appel).
Vérifier l'état sur `GET /api/health` → champs `llm_fallback` et `llm_provider`.
