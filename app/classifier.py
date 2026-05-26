"""
Classification des transactions vers les catégories du marché saoudien.

Approche hybride (cf. spec technique) :
  Niveau 1 — Règles rapides par mots-clés (gratuit, couvre 40-60%)
  Niveau 2 — TODO : similarité par embeddings (transactions déjà classées)
  Niveau 3 — TODO_LLM : appel LLM en batch pour les cas ambigus restants

Toute transaction sous le seuil de confiance est marquée needs_review=True
pour validation humaine (human-in-the-loop).
"""

CONFIDENCE_THRESHOLD = 0.70

# Indices de direction dans le libellé.
# Servent UNIQUEMENT à détecter une contradiction avec le signe du montant.
INFLOW_HINTS = ["incoming", "وارد", "تحويل وارد", "deposit", "إيداع", "customer payment", "تحصيل", "refund", "استرداد"]
OUTFLOW_HINTS = ["outgoing", "صادر", "withdrawal", "سحب", "payment to", "دفعة", "supplier payment", "سداد"]

# Règles : (mots-clés, catégorie, confiance)
RULES = [
    (["راتب", "رواتب", "مسير", "salary", "payroll"], "رواتب", 0.97),
    (["zatca", "ضريبة القيمة", "القيمة المضافة", "vat", "هيئة الزكاة", "زكاة"], "ضريبة ق.م وزكاة", 0.96),
    (["gosi", "التأمينات", "تأمينات اجتماعية"], "ضريبة ق.م وزكاة", 0.92),
    (["إيجار", "rent", "ايجار"], "إيجارات ومرافق", 0.94),
    (["كهرباء", "sec", "المياه", "مياه", "stc", "الاتصالات", "فاتورة"], "إيجارات ومرافق", 0.85),
    (["مورد", "supplier", "توريد", "معدات", "supplies"], "موردون", 0.88),
    (["رسوم", "خدمات بنكية", "service charge", "fee", "عمولة"], "رسوم بنكية", 0.93),
    (["مبيعات", "نقطة بيع", "pos", "mada", "تحصيل"], "تحصيل عملاء", 0.86),
    (["تحويل وارد", "incoming", "وارد", "customer payment"], "تحصيل عملاء", 0.78),
]


def _expected_direction(desc: str) -> str | None:
    """
    Devine le sens suggéré par le libellé : 'in', 'out', ou None si ambigu.
    """
    has_in = any(h.lower() in desc for h in INFLOW_HINTS)
    has_out = any(h.lower() in desc for h in OUTFLOW_HINTS)
    if has_in and not has_out:
        return "in"
    if has_out and not has_in:
        return "out"
    return None  # aucun indice, ou les deux (ambigu)


def _check_consistency(desc: str, amount: float) -> str | None:
    """
    Compare le sens du libellé au signe du montant.
    Retourne une raison de revue si contradiction, sinon None.
    """
    expected = _expected_direction(desc)
    if expected is None or amount == 0:
        return None
    actual = "in" if amount > 0 else "out"
    if expected != actual:
        if expected == "in":
            return "libellé d'entrée mais montant négatif (sortie) — à vérifier"
        else:
            return "libellé de sortie mais montant positif (entrée) — à vérifier"
    return None


def classify(description: str, amount: float) -> dict:
    """
    Retourne {category, confidence, needs_review, review_reason, counterparty}.
    Détecte aussi les contradictions entre libellé et signe du montant.
    """
    desc = (description or "").lower()

    # détection de cohérence directionnelle (indépendante de la catégorie)
    inconsistency = _check_consistency(desc, amount)

    for keywords, category, conf in RULES:
        if any(kw.lower() in desc for kw in keywords):
            needs_review = conf < CONFIDENCE_THRESHOLD or inconsistency is not None
            return {
                "category": category,
                "confidence": conf if inconsistency is None else min(conf, 0.5),
                "needs_review": needs_review,
                "review_reason": inconsistency,
                "counterparty": _extract_counterparty(description),
                "method": "rules",
            }

    # ---- TODO niveau 2 : recherche par similarité d'embeddings ----
    #   vec = embed(desc); match = nearest(vec)
    #   if match.similarity > 0.85: return match.category ...

    # ---- TODO_LLM niveau 3 : batch vers le LLM ----
    #   voir app/llm_stub.py -> classify_batch()
    #   Pour le MVP, fallback : non classé + revue humaine
    return {
        "category": "غير مصنّف",
        "confidence": 0.40,
        "needs_review": True,
        "review_reason": inconsistency,
        "counterparty": _extract_counterparty(description),
        "method": "fallback",
    }


def _extract_counterparty(description: str) -> str:
    """Extraction naïve du tiers : ce qui suit un tiret."""
    if not description:
        return ""
    if " - " in description:
        return description.split(" - ", 1)[1].strip()
    return ""
