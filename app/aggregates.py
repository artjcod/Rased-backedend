"""
Logique d'agrégation pure (sans dépendance à MongoDB).
Prend une liste de dicts de transactions, retourne les agrégats.
Séparé pour être testable unitairement et réutilisable.
"""


def compute_summary(txs: list[dict]) -> dict:
    """
    txs : liste de dicts ayant au moins {date, amount, balance, category, needs_review}
    Retourne les agrégats (solde courant, flux, catégories, récentes, série).
    """
    if not txs:
        return {"empty": True}

    # tri par date croissante pour le solde courant et la série
    by_date_asc = sorted(txs, key=lambda t: t["date"])

    with_bal = [t for t in by_date_asc if t.get("balance") is not None]
    current_balance = with_bal[-1]["balance"] if with_bal else sum(t["amount"] for t in txs)

    inflow = sum(t["amount"] for t in txs if t["amount"] > 0)
    outflow = sum(-t["amount"] for t in txs if t["amount"] < 0)

    cat_map = {}
    for t in txs:
        if t["amount"] < 0:
            cat_map[t["category"]] = cat_map.get(t["category"], 0) + abs(t["amount"])
    total_exp = sum(cat_map.values()) or 1
    categories = sorted(
        [{"name": k, "amount": round(v, 2), "pct": round(v / total_exp * 100)} for k, v in cat_map.items()],
        key=lambda c: -c["amount"],
    )

    recent = sorted(txs, key=lambda t: t["date"], reverse=True)[:6]
    needs_review = sum(1 for t in txs if t.get("needs_review"))
    series = [{"date": t["date"], "balance": t["balance"]} for t in with_bal]

    return {
        "empty": False,
        "current_balance": round(current_balance, 2),
        "inflow": round(inflow, 2),
        "outflow": round(outflow, 2),
        "net": round(inflow - outflow, 2),
        "count": len(txs),
        "needs_review": needs_review,
        "categories": categories,
        "recent": recent,
        "series": series,
    }
