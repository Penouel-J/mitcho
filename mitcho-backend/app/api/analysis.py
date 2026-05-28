import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.data.wfp_loader import fetch_latest_prices
from app.rag.generator import generate_analysis, generate_chat_reply, generate_page_sections
from app.rag.vector_store import collection_count
from db.models import User

# ── Cache mémoire pour les sections de page (évite un appel LLM à chaque visite) ──
# Clé : (profile, month_key)  — TTL : 4 heures
_sections_cache: dict[str, dict] = {}
_CACHE_TTL = 4 * 3600  # secondes

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    profile: str = "decideur"  # "agriculteur" | "decideur"


class ChatResponse(BaseModel):
    reply: str
    context_docs: int


@router.get("/status")
async def knowledge_base_status():
    """Returns the current state of the knowledge base."""
    return {
        "documents_indexed": collection_count(),
        "status": "ready" if collection_count() > 0 else "empty",
    }


@router.post("/generate")
async def generate_monthly_analysis(current_user: User = Depends(get_current_user)):
    """
    Triggers a full RAG analysis pipeline (authenticated users only).
    Fetches WFP prices, retrieves GDELT context, generates analysis via LLM.
    This can take 15-30 seconds depending on data availability.
    """
    try:
        price_data = await fetch_latest_prices()
        prices = price_data.get("prices", [])
        profile = getattr(current_user, "profile", "decideur")
        result = await generate_analysis(prices=prices, profile=profile)
        return {
            "month": result["month"],
            "analysis": result["analysis"],
            "tokens_used": result["tokens_used"],
            "prices_count": len(prices),
            "context_docs": collection_count(),
            "profile": profile,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération: {str(exc)}")


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """
    RAG-powered chatbot endpoint (public — no auth required).
    The LLM receives the query + relevant context from the knowledge base.
    """
    try:
        reply = await generate_chat_reply(body.message, body.history, profile=body.profile)
        return ChatResponse(reply=reply, context_docs=collection_count())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Page sections endpoint ───────────────────────────────────────────────────

class SectionsRequest(BaseModel):
    profile: str = "citoyen"   # decideur | commercant | citoyen
    force_refresh: bool = False


@router.post("/sections")
async def get_page_sections(body: SectionsRequest):
    """
    Génère (ou retourne depuis le cache) le contenu structuré de la page tendances.html.
    Retourne : hero_subtitle, situation_summary_html, 3 recommandations, alert_tags, risk_score, risk_label.
    Cache de 4h par (profil × mois).
    """
    from datetime import datetime
    month_key  = datetime.now().strftime("%Y-%m")
    cache_key  = f"{body.profile}_{month_key}"
    now        = time.time()

    if not body.force_refresh:
        cached = _sections_cache.get(cache_key)
        if cached and (now - cached["_cached_at"]) < _CACHE_TTL:
            return cached["data"]

    try:
        price_data = await fetch_latest_prices()
        prices     = price_data.get("prices", [])
        data = await generate_page_sections(
            prices=prices,
            month_label=datetime.now().strftime("%B %Y").capitalize(),
            profile=body.profile,
        )
        _sections_cache[cache_key] = {"data": data, "_cached_at": now}
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Génération sections échouée: {exc}")


# ── GDELT re-ingestion endpoint ───────────────────────────────────────────────

class GdeltIngestResponse(BaseModel):
    chunks_indexed: int
    source: str


@router.post("/gdelt/ingest", response_model=GdeltIngestResponse)
async def reingest_gdelt(current_user: User = Depends(get_current_user)):
    """
    Réindexe les données historiques GDELT depuis le CSV local (authenticated uniquement).
    Utile après mise à jour du fichier gdelt_data.csv.
    """
    try:
        from app.data.scheduler import ingest_gdelt_csv
        n = await ingest_gdelt_csv()
        return GdeltIngestResponse(chunks_indexed=n, source="gdelt_csv")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion CSV échouée: {exc}")
