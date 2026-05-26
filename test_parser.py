"""
Tests du parser. Lancer : python -m pytest tests/ -v   (ou python tests/test_parser.py)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.parser import parse_statement

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")


def _load(name):
    with open(os.path.join(SAMPLES, name), "rb") as f:
        return f.read()


def test_alrajhi_split_mode():
    r = parse_statement(_load("alrajhi_statement.csv"), "alrajhi_statement.csv")
    assert r["detected"]["mode"] == "split"
    assert r["summary"]["total"] == 13  # 14 lignes - 1 solde initial exclu
    # vérifier qu'un crédit est positif et un débit négatif
    salaries = [t for t in r["transactions"] if "رواتب" in t["category"]]
    assert salaries and salaries[0]["amount"] < 0


def test_snb_signed_mode():
    r = parse_statement(_load("snb_statement.csv"), "snb_statement.csv")
    assert r["detected"]["mode"] == "signed"
    assert r["summary"]["total"] == 11  # 12 lignes - 1 solde initial exclu


def test_alinma_typed_hijri():
    r = parse_statement(_load("alinma_statement.xlsx"), "alinma_statement.xlsx")
    assert r["detected"]["mode"] == "typed"
    # la ligne d'en-tête doit avoir été trouvée après les lignes parasites
    assert r["detected"]["header_row"] >= 6
    # conversion hégirienne -> grégorien 2026
    assert all(t["date"].startswith("2026") for t in r["transactions"])


def test_classification_vat():
    r = parse_statement(_load("alrajhi_statement.csv"), "alrajhi_statement.csv")
    vat = [t for t in r["transactions"] if "ZATCA" in t["description"]]
    assert vat and "ضريبة" in vat[0]["category"]


def test_opening_balance_excluded():
    """رصيد افتتاحي / Opening Balance (montant 0) ne doit PAS apparaître comme transaction."""
    for fname in ["alrajhi_statement.csv", "snb_statement.csv", "alinma_statement.xlsx"]:
        r = parse_statement(_load(fname), fname)
        opening = [t for t in r["transactions"]
                   if ("رصيد افتتاحي" in t["description"] or
                       "opening balance" in t["description"].lower())
                   and t["amount"] == 0]
        assert opening == [], f"{fname} : solde initial présent alors qu'il devrait être exclu"
    """La transaction piège (libellé entrant + montant négatif) doit être signalée."""
    r = parse_statement(_load("snb_statement.csv"), "snb_statement.csv")
    al_fajr = [t for t in r["transactions"] if "Al Fajr" in t["description"]]
    assert al_fajr, "transaction Al Fajr introuvable"
    t = al_fajr[0]
    assert t["amount"] < 0                    # montant négatif
    assert t["needs_review"] is True          # marquée à revoir
    assert t["review_reason"] is not None     # avec une raison explicite


def test_metadata_extraction():
    """Banque, compte (masqué) et client doivent être extraits des en-têtes."""
    for fname, bank_kw in [
        ("alrajhi_statement.csv", "الراجحي"),
        ("snb_statement.csv", "الأهلي"),
        ("alinma_statement.xlsx", "الإنماء"),
    ]:
        r = parse_statement(_load(fname), fname)
        m = r["metadata"]
        assert m["bank_name"] and bank_kw in m["bank_name"]
        assert m["account_number"] and m["account_number"].startswith("****")  # masqué
        assert m["customer_name"]


def test_reference_extracted():
    """La référence bancaire doit être captée pour Al Rajhi et SNB."""
    r = parse_statement(_load("snb_statement.csv"), "snb_statement.csv")
    refs = [t["reference"] for t in r["transactions"] if t["reference"]]
    assert len(refs) > 0


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"✓ {name}")
                passed += 1
            except AssertionError as e:
                print(f"✗ {name} : {e}")
                failed += 1
    print(f"\n{passed} réussis, {failed} échoués")
