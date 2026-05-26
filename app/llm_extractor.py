"""
Intégration LLM — utilisée UNIQUEMENT en repli des règles.

Supporte deux fournisseurs, sélectionnés automatiquement selon la clé présente :
  - Google Gemini (niveau gratuit)  -> GEMINI_API_KEY
  - Anthropic Claude (payant)        -> ANTHROPIC_API_KEY

Principe : les règles tentent d'abord (gratuit, instantané). Si elles
échouent à extraire une info, on appelle le LLM pour la retrouver.

Dégradation gracieuse : si aucune clé n'est configurée ou si l'appel échoue,
les fonctions retournent {} sans lever d'exception. Le système continue
de fonctionner avec ce que les règles ont trouvé.
"""
import json
import os
import re

# Modèles par défaut (économiques, suffisants pour de l'extraction)
GEMINI_MODEL = "gemini-1.5-flash"          # disponible sur le free tier
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

METADATA_PROMPT = """Tu es un expert en extraits bancaires du Golfe (Arabie Saoudite).
On te donne les premières lignes d'un relevé bancaire (avant le tableau de transactions).
Extrais les métadonnées et réponds UNIQUEMENT en JSON valide, sans aucun texte autour :
{"bank_name": "<nom de la banque ou null>",
 "account_number": "<numéro/IBAN complet ou null>",
 "customer_name": "<nom du client ou null>",
 "period": "<période du relevé ou null>",
 "currency": "<devise ou null>"}
Si une information est absente, mets null. Ne devine pas."""


def _get_key(env_name: str, settings_attr: str):
    """Récupère une clé depuis l'environnement ou la config de l'app."""
    key = os.environ.get(env_name)
    if not key:
        try:
            from .config import settings
            key = getattr(settings, settings_attr, "") or None
        except Exception:
            key = None
    return key or None


def _provider():
    """Détermine le fournisseur disponible : 'gemini', 'claude', ou None."""
    if _get_key("GEMINI_API_KEY", "gemini_api_key"):
        return "gemini"
    if _get_key("ANTHROPIC_API_KEY", "anthropic_api_key"):
        return "claude"
    return None


def is_available() -> bool:
    """Indique si un repli LLM est utilisable."""
    return _provider() is not None


def _mask_account(acc):
    if not acc:
        return None
    digits = re.sub(r"\s+", "", str(acc))
    if len(digits) <= 4:
        return digits
    return "****" + digits[-4:]


def _clean_json(text: str) -> str:
    """Nettoie une réponse LLM pour ne garder que le JSON."""
    text = text.strip()
    if text.startswith("```"):
        # enlever les fences ```json ... ```
        text = text.split("```")[1]
        text = text.replace("json", "", 1).strip()
    return text


def _call_gemini(header_text: str) -> str | None:
    """Appel à l'API Gemini. Retourne le texte brut de la réponse ou None."""
    key = _get_key("GEMINI_API_KEY", "gemini_api_key")
    if not key:
        return None
    try:
        # SDK officiel google-generativeai
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=METADATA_PROMPT)
        resp = model.generate_content(header_text[:2000])
        return resp.text
    except Exception:
        return None


def _call_claude(header_text: str) -> str | None:
    """Appel à l'API Claude. Retourne le texte brut de la réponse ou None."""
    key = _get_key("ANTHROPIC_API_KEY", "anthropic_api_key")
    if not key:
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=METADATA_PROMPT,
            messages=[{"role": "user", "content": header_text[:2000]}],
        )
        return "".join(b.text for b in resp.content if hasattr(b, "text"))
    except Exception:
        return None


def extract_metadata_llm(header_text: str) -> dict:
    """
    Extrait les métadonnées via le LLM disponible (Gemini en priorité, sinon Claude).
    Retourne {} si indisponible ou en cas d'erreur (dégradation gracieuse).
    Le numéro de compte est masqué avant d'être retourné.
    """
    if not header_text.strip():
        return {}

    provider = _provider()
    if provider is None:
        return {}

    raw = _call_gemini(header_text) if provider == "gemini" else _call_claude(header_text)
    if not raw:
        return {}

    try:
        data = json.loads(_clean_json(raw))
        # masquer le compte par sécurité, ne jamais stocker le numéro complet
        if data.get("account_number"):
            data["account_number"] = _mask_account(data["account_number"])
        return data
    except Exception:
        return {}


def active_provider() -> str | None:
    """Expose le fournisseur actif (pour le health check)."""
    return _provider()
