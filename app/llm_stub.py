"""
Point d'extension LLM (non actif dans le MVP).

Ce module définit le CONTRAT d'interface pour brancher Claude/GPT plus tard,
sans changer le reste du code. Deux usages :

  1. Détection de schéma ambigu  -> detect_schema_llm()
  2. Classification en batch      -> classify_batch_llm()

Pour activer : implémenter les appels API à l'intérieur, puis décommenter
les blocs TODO_LLM dans schema_detector.py et classifier.py.
"""

# Exemple de prompt système pour la détection de schéma :
SCHEMA_PROMPT = """Tu es un expert en extraits bancaires du Golfe.
On te donne les en-têtes et 3 lignes d'exemple d'un fichier.
Réponds UNIQUEMENT en JSON avec ce format exact, sans texte autour :
{"mapping": {"date": <index>, "description": <index>, "amount": <index|null>,
"debit": <index|null>, "credit": <index|null>, "balance": <index|null>},
"mode": "split|signed|typed"}"""

CLASSIFY_PROMPT = """Tu classes des transactions bancaires saoudiennes.
Catégories autorisées : رواتب، موردون، إيجارات ومرافق، ضريبة ق.م وزكاة،
تحصيل عملاء، رسوم بنكية، تشغيل أخرى، غير مصنّف.
Pour chaque transaction, réponds en JSON : liste de
{"category": "...", "confidence": 0.0-1.0, "counterparty": "..."}"""


def detect_schema_llm(headers, sample_rows):
    """À implémenter : appel LLM renvoyant le mapping. Lève NotImplementedError pour l'instant."""
    raise NotImplementedError("Brancher l'API Claude ici (voir SCHEMA_PROMPT).")


def classify_batch_llm(descriptions: list[str]):
    """À implémenter : classification en batch (50 transactions/appel pour réduire le coût)."""
    raise NotImplementedError("Brancher l'API Claude ici (voir CLASSIFY_PROMPT).")
