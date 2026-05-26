"""
Détection automatique de la structure d'un extrait bancaire.

Stratégie en 2 niveaux :
  1. Détection par règles (mots-clés multilingues) — rapide, gratuit, couvre la majorité.
  2. Fallback LLM — pour les fichiers dont la structure reste ambiguë.
     (point d'extension marqué TODO_LLM ci-dessous)

Le schéma unifié cible : date, description, amount (signé), balance, ref
"""
import re

# Dictionnaires de synonymes par champ (arabe + anglais)
FIELD_KEYWORDS = {
    "date": ["date", "التاريخ", "تاريخ", "اليوم", "hijri", "هجري", "ميلادي"],
    "description": ["description", "البيان", "الوصف", "بيان", "تفاصيل", "details", "narrative", "particulars"],
    "debit": ["debit", "مدين", "سحب", "withdrawal", "out", "صادر"],
    "credit": ["credit", "دائن", "إيداع", "deposit", "in", "وارد"],
    "amount": ["amount", "المبلغ", "مبلغ", "value", "القيمة", "حركة"],
    "balance": ["balance", "الرصيد", "رصيد", "running balance"],
    "type": ["نوع الحركة", "type", "نوع", "movement", "حركة", "dr/cr"],
    "ref": ["reference", "ref", "رقم العملية", "المرجع", "رقم", "id", "transaction"],
}


def _match_field(header: str) -> str | None:
    h = header.strip().lower()
    # ordre de priorité : champs spécifiques avant 'amount' générique
    for field in ["date", "balance", "debit", "credit", "type", "ref", "description", "amount"]:
        for kw in FIELD_KEYWORDS[field]:
            if kw.lower() in h:
                return field
    return None


def detect_schema(headers: list[str]) -> dict:
    """
    Retourne un mapping {champ_unifié: index_colonne}.
    Détermine aussi le 'mode' du montant :
      - 'split'  : colonnes débit + crédit séparées
      - 'signed' : une seule colonne montant (signe = sens)
      - 'typed'  : montant positif + colonne type (مدين/دائن)
    """
    mapping = {}
    for idx, h in enumerate(headers):
        field = _match_field(str(h))
        if field and field not in mapping:
            mapping[field] = idx

    # déterminer le mode du montant
    if "debit" in mapping and "credit" in mapping:
        mode = "split"
    elif "amount" in mapping and "type" in mapping:
        mode = "typed"
    elif "amount" in mapping:
        mode = "signed"
    elif "credit" in mapping or "debit" in mapping:
        mode = "split"
    else:
        mode = "unknown"

    confidence = _confidence(mapping, mode)
    return {"mapping": mapping, "mode": mode, "confidence": confidence}


def _confidence(mapping: dict, mode: str) -> float:
    score = 0.0
    if "date" in mapping:
        score += 0.35
    if "description" in mapping:
        score += 0.30
    if mode != "unknown":
        score += 0.30
    if "balance" in mapping:
        score += 0.05
    return round(min(score, 1.0), 2)


def find_header_row(rows: list[list], max_scan: int = 15) -> int:
    """
    Trouve l'index de la ligne d'en-tête réelle (saute les lignes parasites).
    Heuristique : la ligne qui matche le plus de champs connus.
    """
    best_idx, best_score = 0, -1
    for i, row in enumerate(rows[:max_scan]):
        cells = [str(c) for c in row if c is not None and str(c).strip()]
        if len(cells) < 2:
            continue
        matched = sum(1 for c in cells if _match_field(c))
        if matched > best_score:
            best_score, best_idx = matched, i
    return best_idx


# ----------------------------------------------------------------------------
# TODO_LLM : si confidence < seuil, appeler le LLM ici.
# Exemple d'intégration (pseudo-code) :
#
#   if schema["confidence"] < 0.6:
#       schema = call_llm_schema_detection(headers, sample_rows)
#
# Le LLM reçoit les en-têtes + 3 lignes d'exemple et renvoie le mapping JSON.
# Voir app/llm_stub.py pour le contrat d'interface.
# ----------------------------------------------------------------------------
