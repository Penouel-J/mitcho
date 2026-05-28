import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.core.config import settings
from app.data.wfp_loader import fetch_latest_prices
from app.rag.generator import generate_analysis, generate_chat_reply
from app.rag.vector_store import collection_count
from db.models import User

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


# ── GDELT BigQuery ingestion endpoints ────────────────────────────────────────

class GdeltIngestRequest(BaseModel):
    target_month: str  # "YYYY-MM"


class GdeltIngestResponse(BaseModel):
    chunks_indexed: int
    target_month: str
    source: str


@router.post("/gdelt/ingest", response_model=GdeltIngestResponse)
async def ingest_gdelt_month(
    body: GdeltIngestRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Déclenche l'ingestion GDELT pour un mois spécifique (admin/authenticated uniquement).
    Utilise BigQuery si GOOGLE_CLOUD_PROJECT est configuré, sinon le DOC API.

    body.target_month : "YYYY-MM" (ex: "2026-05")
    """
    if not re.match(r"^\d{4}-\d{2}$", body.target_month):
        raise HTTPException(status_code=400, detail="Format invalide. Attendu: YYYY-MM (ex: 2026-05)")

    if settings.GOOGLE_CLOUD_PROJECT:
        try:
            from app.data.gdelt_bq_loader import ingest_month
            n = await ingest_month(
                project_id=settings.GOOGLE_CLOUD_PROJECT,
                target_month=body.target_month,
            )
            return GdeltIngestResponse(
                chunks_indexed=n,
                target_month=body.target_month,
                source="bigquery",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"BigQuery ingestion failed: {exc}")
    else:
        # DOC API fallback — ignore target_month, fetch last 7 days
        try:
            from app.data.gdelt_loader import fetch_gdelt_articles, articles_to_rag_chunks
            from app.rag.vector_store import upsert_chunks
            articles = await fetch_gdelt_articles(timespan="7d")
            chunks   = articles_to_rag_chunks(articles)
            n = upsert_chunks(chunks) if chunks else 0
            return GdeltIngestResponse(
                chunks_indexed=n,
                target_month=body.target_month,
                source="doc_api_fallback",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"DOC API ingestion failed: {exc}")
