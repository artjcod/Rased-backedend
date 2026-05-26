"""
Modèles de documents MongoDB via Beanie (ODM).

Collections :
  - companies     : entreprises (multi-tenant, simplifié pour le MVP)
  - uploads       : métadonnées de chaque relevé importé
  - transactions  : transactions normalisées et classées (collection principale)

Beanie = équivalent ODM d'un ORM, basé sur Pydantic + Motor (async).
"""
from datetime import datetime, date
from typing import Optional
from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class Company(Document):
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "companies"


class Upload(Document):
    company_id: Optional[PydanticObjectId] = None
    filename: str
    detected_mode: str                 # split | signed | typed
    detected_confidence: float
    header_row: int = 0
    total_transactions: int = 0

    # métadonnées extraites de l'en-tête du relevé
    bank_name: Optional[str] = None
    account_number: Optional[str] = None   # masqué (4 derniers chiffres)
    customer_name: Optional[str] = None
    period: Optional[str] = None
    currency: Optional[str] = None

    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "uploads"


class Transaction(Document):
    upload_id: Indexed(PydanticObjectId)         # indexé pour requêtes rapides
    company_id: Optional[PydanticObjectId] = None

    date: date
    description: str = ""
    amount: float                                # signé : + = crédit, - = débit
    balance: Optional[float] = None
    reference: Optional[str] = None              # réf bancaire (anti-doublon)
    movement_type: Optional[str] = None          # مدين/دائن si fourni

    category: str = "غير مصنّف"
    counterparty: str = ""
    confidence: float = 0.0
    needs_review: bool = True
    review_reason: Optional[str] = None       # ex : contradiction libellé/signe

    # Traçabilité : la catégorie a-t-elle été corrigée manuellement ?
    manually_labeled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "transactions"


# Liste exposée à l'initialisation Beanie
ALL_MODELS = [Company, Upload, Transaction]
