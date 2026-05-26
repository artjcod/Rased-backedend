"""
Extraction des métadonnées d'en-tête d'un relevé bancaire.
Lit les lignes AVANT le tableau de transactions pour en tirer :
  bank_name, account_number (masqué), customer_name, period, currency.

Robuste à l'absence : si une info manque, le champ reste None.
"""
import re

# Banques connues (motif -> nom normalisé)
KNOWN_BANKS = [
    (r"الراجحي|al\s*rajhi|rajhi", "مصرف الراجحي"),
    (r"الأهلي|الاهلي|snb|saudi national bank|al\s*ahli", "البنك الأهلي السعودي"),
    (r"الإنماء|الانماء|alinma", "مصرف الإنماء"),
    (r"الرياض|riyad bank", "بنك الرياض"),
    (r"سامبا|samba", "سامبا"),
    (r"البلاد|albilad|al\s*bilad", "بنك البلاد"),
    (r"ساب|sabb", "البنك السعودي البريطاني (ساب)"),
]

# Étiquettes pour numéro de compte / IBAN
ACCOUNT_LABELS = ["رقم الحساب", "account number", "account no", "iban", "الآيبان"]
CUSTOMER_LABELS = ["اسم العميل", "customer", "customer name", "client", "العميل"]
PERIOD_LABELS = ["الفترة", "period", "statement period", "من", "from"]
CURRENCY_LABELS = ["العملة", "currency"]


def _mask_account(acc: str) -> str:
    """Masque le numéro de compte : ne garde que les 4 derniers caractères significatifs."""
    digits = re.sub(r"\s+", "", acc)
    if len(digits) <= 4:
        return digits
    return "****" + digits[-4:]


def _find_bank(text: str) -> str | None:
    low = text.lower()
    for pattern, name in KNOWN_BANKS:
        if re.search(pattern, low):
            return name
    return None


def _extract_after_label(line: str, labels: list[str]) -> str | None:
    """Si la ligne contient une étiquette connue, retourne ce qui suit ':'."""
    low = line.lower()
    for lab in labels:
        if lab.lower() in low:
            # prend la partie après ':' si présent, sinon après l'étiquette
            if ":" in line:
                return line.split(":", 1)[1].strip()
            idx = low.find(lab.lower()) + len(lab)
            return line[idx:].strip(" :")
    return None


def extract_metadata(header_rows: list[list], filename: str = "") -> dict:
    """
    header_rows : les lignes AVANT le tableau (peuvent être vides ou parasites).
    Retourne un dict avec bank_name, account_number, customer_name, period, currency.
    """
    meta = {
        "bank_name": None,
        "account_number": None,
        "customer_name": None,
        "period": None,
        "currency": None,
    }

    # joindre toutes les cellules de chaque ligne en texte
    lines = []
    for row in header_rows:
        cells = [str(c) for c in row if c is not None and str(c).strip()]
        if cells:
            lines.append(" ".join(cells))

    full_text = " \n ".join(lines)

    # banque : chercher dans tout l'en-tête, sinon dans le nom de fichier
    meta["bank_name"] = _find_bank(full_text) or _find_bank(filename)

    # parcourir ligne par ligne pour les champs étiquetés
    for line in lines:
        if meta["account_number"] is None:
            acc = _extract_after_label(line, ACCOUNT_LABELS)
            if acc:
                meta["account_number"] = _mask_account(acc)
        if meta["customer_name"] is None:
            cust = _extract_after_label(line, CUSTOMER_LABELS)
            if cust:
                meta["customer_name"] = cust
        if meta["period"] is None:
            per = _extract_after_label(line, PERIOD_LABELS)
            if per:
                meta["period"] = per
        if meta["currency"] is None:
            cur = _extract_after_label(line, CURRENCY_LABELS)
            if cur:
                meta["currency"] = cur

    # devise par défaut
    if meta["currency"] is None and ("sar" in full_text.lower() or "ريال" in full_text):
        meta["currency"] = "SAR"

    # ---- Repli LLM : si des champs essentiels manquent encore ----
    # On n'appelle le LLM QUE si les règles ont échoué, et seulement s'il est dispo.
    essential_missing = meta["bank_name"] is None or meta["account_number"] is None
    if essential_missing:
        try:
            from .llm_extractor import extract_metadata_llm, is_available
            if is_available():
                llm_meta = extract_metadata_llm(full_text)
                # ne compléter QUE les champs manquants (les règles ont priorité)
                for key in ["bank_name", "account_number", "customer_name", "period", "currency"]:
                    if meta[key] is None and llm_meta.get(key):
                        meta[key] = llm_meta[key]
                meta["_llm_used"] = bool(llm_meta)
        except Exception:
            pass  # dégradation gracieuse : on garde ce que les règles ont trouvé

    return meta
