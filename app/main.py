"""
API Rased — backend avec persistance MongoDB (Beanie ODM).

Endpoints :
  POST   /api/upload                          → importe et PERSISTE un relevé
  GET    /api/uploads                         → liste des relevés importés
  GET    /api/transactions                    → liste des transactions (filtrable)
  GET    /api/summary                         → agrégats calculés depuis la base
  PATCH  /api/transactions/{id}               → met à jour le label / reclassifie
  DELETE /api/transactions/{id}               → supprime une transaction
  GET    /api/health
"""
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from beanie import PydanticObjectId
from beanie.operators import In

from .config import settings
from .database import init_db, close_db
from .models import Upload, Transaction
from .parser import parse_statement
from .classifier import classify, CONFIDENCE_THRESHOLD
from .aggregates import compute_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Rased Treasury API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXT = (".csv", ".tsv", ".xlsx", ".xls")
MAX_SIZE = 10 * 1024 * 1024


# ---------- Schémas de requête/réponse ----------
class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    counterparty: Optional[str] = None


class ReclassifyRequest(BaseModel):
    # si fourni, applique cette catégorie ; sinon relance le classifieur auto
    category: Optional[str] = None


def tx_to_dict(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "upload_id": str(t.upload_id),
        "date": t.date.isoformat(),
        "description": t.description,
        "amount": round(t.amount, 2),
        "balance": round(t.balance, 2) if t.balance is not None else None,
        "reference": t.reference,
        "movement_type": t.movement_type,
        "category": t.category,
        "counterparty": t.counterparty,
        "confidence": t.confidence,
        "needs_review": t.needs_review,
        "review_reason": t.review_reason,
        "manually_labeled": t.manually_labeled,
    }


# ---------- Vider toutes les données (utile en développement) ----------
@app.delete("/api/reset")
async def reset_all():
    tx_deleted = await Transaction.find_all().delete()
    up_deleted = await Upload.find_all().delete()
    return {
        "ok": True,
        "deleted_transactions": tx_deleted.deleted_count if tx_deleted else 0,
        "deleted_uploads": up_deleted.deleted_count if up_deleted else 0,
    }


# ---------- Health ----------
@app.get("/api/health")
async def health():
    from .llm_extractor import is_available, active_provider
    return {
        "status": "healthy",
        "time": datetime.utcnow().isoformat(),
        "llm_fallback": is_available(),       # True si le repli LLM est activé
        "llm_provider": active_provider(),    # 'gemini', 'claude', ou None
    }


# ---------- Upload + persistance ----------
@app.post("/api/upload")
async def upload_statement(file: UploadFile = File(...)):
    fname = (file.filename or "").lower()
    if not fname.endswith(ALLOWED_EXT):
        raise HTTPException(status_code=400, detail="Format non supporté. Utilisez CSV ou Excel.")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo).")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    try:
        result = parse_statement(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Échec du traitement : {str(e)}")

    if not result.get("transactions"):
        raise HTTPException(status_code=422, detail="Aucune transaction détectée.")

    # 1) persister le document Upload avec ses métadonnées
    det = result["detected"]
    meta = result.get("metadata", {})
    upload = Upload(
        filename=file.filename,
        detected_mode=det["mode"],
        detected_confidence=det["confidence"],
        header_row=det.get("header_row", 0),
        total_transactions=result["summary"]["total"],
        bank_name=meta.get("bank_name"),
        account_number=meta.get("account_number"),
        customer_name=meta.get("customer_name"),
        period=meta.get("period"),
        currency=meta.get("currency"),
    )
    await upload.insert()

    # 2) persister toutes les transactions (insertion en lot)
    docs = []
    for t in result["transactions"]:
        docs.append(Transaction(
            upload_id=upload.id,
            date=date.fromisoformat(t["date"]),
            description=t["description"],
            amount=t["amount"],
            balance=t["balance"],
            reference=t.get("reference"),
            movement_type=t.get("movement_type"),
            category=t["category"],
            counterparty=t["counterparty"],
            confidence=t["confidence"],
            needs_review=t["needs_review"],
            review_reason=t.get("review_reason"),
        ))
    if docs:
        await Transaction.insert_many(docs)

    return {
        "upload_id": str(upload.id),
        "filename": upload.filename,
        "detected": det,
        "summary": result["summary"],
    }


# ---------- Lister les uploads ----------
@app.get("/api/uploads")
async def list_uploads():
    uploads = await Upload.find_all().sort(-Upload.uploaded_at).to_list()
    return [{
        "id": str(u.id),
        "filename": u.filename,
        "detected_mode": u.detected_mode,
        "total_transactions": u.total_transactions,
        "bank_name": u.bank_name,
        "account_number": u.account_number,
        "customer_name": u.customer_name,
        "period": u.period,
        "currency": u.currency,
        "uploaded_at": u.uploaded_at.isoformat(),
    } for u in uploads]


# ---------- Lister les transactions (filtrable par upload) ----------
@app.get("/api/transactions")
async def list_transactions(
    upload_id: Optional[str] = Query(None),
    needs_review: Optional[bool] = Query(None),
):
    query = {}
    if upload_id:
        query["upload_id"] = PydanticObjectId(upload_id)
    if needs_review is not None:
        query["needs_review"] = needs_review

    txs = await Transaction.find(query).sort(-Transaction.date).to_list()
    return [tx_to_dict(t) for t in txs]


# ---------- Agrégats calculés depuis la base ----------
@app.get("/api/summary")
async def get_summary(upload_id: Optional[str] = Query(None)):
    query = {}
    if upload_id:
        query["upload_id"] = PydanticObjectId(upload_id)

    txs = await Transaction.find(query).to_list()
    if not txs:
        return {"empty": True}

    # convertir en dicts pour le module d'agrégation pur
    tx_dicts = [tx_to_dict(t) for t in txs]
    summary = compute_summary(tx_dicts)

    # joindre les métadonnées des comptes (banques/comptes connus)
    uploads = await Upload.find_all().sort(-Upload.uploaded_at).to_list()
    accounts = []
    seen = set()
    for u in uploads:
        key = (u.bank_name, u.account_number)
        if key in seen or not u.bank_name:
            continue
        seen.add(key)
        accounts.append({
            "upload_id": str(u.id),
            "bank_name": u.bank_name,
            "account_number": u.account_number,
            "customer_name": u.customer_name,
            "period": u.period,
            "currency": u.currency,
        })
    summary["accounts"] = accounts
    return summary


# ---------- Mettre à jour un label (étiquetage manuel) ----------
@app.patch("/api/transactions/{tx_id}")
async def update_transaction(tx_id: str, payload: TransactionUpdate):
    t = await Transaction.get(PydanticObjectId(tx_id))
    if not t:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    if payload.category is not None:
        t.category = payload.category
        t.manually_labeled = True
        t.needs_review = False
        t.review_reason = None        # l'humain a tranché
        t.confidence = 1.0
    if payload.description is not None:
        t.description = payload.description
    if payload.counterparty is not None:
        t.counterparty = payload.counterparty

    t.updated_at = datetime.utcnow()
    await t.save()
    return tx_to_dict(t)


# ---------- Reclassifier (auto via le moteur, ou forcer une catégorie) ----------
@app.post("/api/transactions/{tx_id}/reclassify")
async def reclassify_transaction(tx_id: str, payload: ReclassifyRequest):
    t = await Transaction.get(PydanticObjectId(tx_id))
    if not t:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    if payload.category:
        # forcer une catégorie manuellement
        t.category = payload.category
        t.manually_labeled = True
        t.needs_review = False
        t.review_reason = None        # l'humain a tranché
        t.confidence = 1.0
    else:
        # relancer le classifieur automatique
        cls = classify(t.description, t.amount)
        t.category = cls["category"]
        t.counterparty = cls["counterparty"] or t.counterparty
        t.confidence = cls["confidence"]
        t.needs_review = cls["needs_review"]
        t.review_reason = cls.get("review_reason")
        t.manually_labeled = False

    t.updated_at = datetime.utcnow()
    await t.save()
    return tx_to_dict(t)


# ---------- Supprimer une transaction ----------
@app.delete("/api/transactions/{tx_id}")
async def delete_transaction(tx_id: str):
    t = await Transaction.get(PydanticObjectId(tx_id))
    if not t:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")
    await t.delete()
    return {"ok": True, "deleted": tx_id}


# ---------- Supprimer un upload et toutes ses transactions ----------
@app.delete("/api/uploads/{upload_id}")
async def delete_upload(upload_id: str):
    oid = PydanticObjectId(upload_id)
    u = await Upload.get(oid)
    if not u:
        raise HTTPException(status_code=404, detail="Upload introuvable.")
    deleted = await Transaction.find(Transaction.upload_id == oid).delete()
    await u.delete()
    return {"ok": True, "deleted_upload": upload_id, "deleted_transactions": deleted.deleted_count if deleted else 0}
