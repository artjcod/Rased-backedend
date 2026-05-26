"""
Tests de la logique d'agrégation (sans MongoDB).
Lancer : python tests/test_aggregates.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.aggregates import compute_summary

SAMPLE = [
    {"date": "2026-04-01", "amount": 1000.0, "balance": 11000.0, "category": "تحصيل عملاء", "needs_review": False},
    {"date": "2026-04-02", "amount": -300.0, "balance": 10700.0, "category": "موردون", "needs_review": False},
    {"date": "2026-04-03", "amount": -200.0, "balance": 10500.0, "category": "رواتب", "needs_review": True},
]


def test_empty():
    assert compute_summary([]) == {"empty": True}


def test_balances_and_flows():
    s = compute_summary(SAMPLE)
    assert s["empty"] is False
    assert s["current_balance"] == 10500.0   # dernier solde
    assert s["inflow"] == 1000.0
    assert s["outflow"] == 500.0
    assert s["net"] == 500.0
    assert s["count"] == 3
    assert s["needs_review"] == 1


def test_categories_sorted():
    s = compute_summary(SAMPLE)
    cats = s["categories"]
    # seules les dépenses comptent (2 catégories)
    assert len(cats) == 2
    # triées par montant décroissant
    assert cats[0]["amount"] >= cats[1]["amount"]
    # pourcentages cohérents
    assert cats[0]["name"] == "موردون"  # 300 > 200


def test_series_only_with_balance():
    s = compute_summary(SAMPLE)
    assert len(s["series"]) == 3
    assert s["series"][0]["date"] == "2026-04-01"


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
