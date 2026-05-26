"""
Utilitaires de normalisation : dates (hégirien <-> grégorien), montants, texte.
Aucune dépendance externe — conversion hégirienne par algorithme arithmétique.
"""
from datetime import date, datetime
import re


# ----------------------------------------------------------------------------
# Conversion hégirien -> grégorien (algorithme arithmétique Umm al-Qura approximé)
# Suffisant pour le MVP. En production : remplacer par la table officielle Umm al-Qura.
# ----------------------------------------------------------------------------
def hijri_to_gregorian(hy: int, hm: int, hd: int) -> date:
    # Conversion via le nombre de jours Julien (Kuwaiti algorithm)
    jd = (
        int((11 * hy + 3) / 30)
        + 354 * hy
        + 30 * hm
        - int((hm - 1) / 2)
        + hd
        + 1948440
        - 385
    )
    # Julien -> grégorien
    if jd > 2299160:
        l = jd + 68569
        n = int((4 * l) / 146097)
        l = l - int((146097 * n + 3) / 4)
        i = int((4000 * (l + 1)) / 1461001)
        l = l - int((1461 * i) / 4) + 31
        j = int((80 * l) / 2447)
        d = l - int((2447 * j) / 80)
        l = int(j / 11)
        m = j + 2 - 12 * l
        y = 100 * (n - 49) + i + l
    else:
        l = jd + 1402
        n = int((l - 1) / 1461)
        i = l - 1461 * n
        j = int((i - 1) / 365) - int(i / 1461)
        k = i - 365 * j + 30
        m = int((80 * k) / 2447)
        d = k - int((2447 * m) / 80)
        k = int(m / 11)
        m = m + 2 - 12 * k
        y = 4 * n + j + k - 4716
    return date(y, m, d)


# Détecte si une chaîne ressemble à une date hégirienne (année 1300-1500)
def looks_hijri(s: str) -> bool:
    m = re.search(r"\b(1[34]\d{2})\b", s)
    if not m:
        return False
    # un marqueur explicite renforce, mais l'année suffit
    return True


def parse_date(raw) -> date | None:
    """Parse une date dans plusieurs formats, retourne toujours du grégorien."""
    if raw is None:
        return None
    if isinstance(raw, (datetime, date)):
        return raw.date() if isinstance(raw, datetime) else raw

    s = str(raw).strip()
    if not s:
        return None
    # retirer un éventuel suffixe هـ ou هجري
    s = re.sub(r"\s*(هـ|هجري|H)\s*$", "", s).strip()

    # extraire les composants numériques
    parts = re.split(r"[/\-\.]", s)
    if len(parts) != 3:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None

    # déterminer l'ordre (année en premier si 4 chiffres au début)
    if nums[0] > 1000:
        y, mo, d = nums[0], nums[1], nums[2]
    else:
        d, mo, y = nums[0], nums[1], nums[2]

    # hégirien si l'année est dans la plage 1300-1500
    if 1300 <= y <= 1500:
        try:
            return hijri_to_gregorian(y, mo, d)
        except Exception:
            return None
    # sinon grégorien
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_amount(raw) -> float | None:
    """Parse un montant : gère virgules, espaces, parenthèses (négatif), vide."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = True
        s = s[1:]
    # retirer séparateurs de milliers et symboles
    s = re.sub(r"[^\d.,]", "", s)
    s = s.replace(",", "")
    if not s:
        return None
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def clean_description(raw) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    s = re.sub(r"\s+", " ", s)
    return s
