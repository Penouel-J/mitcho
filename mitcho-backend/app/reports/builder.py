"""
Assembles all data needed to build a MITCHÔ monthly report.
Orchestrates: WFP prices fetch → RAG analysis generation.

NOTE: Indexing into the vector store is handled exclusively by the background
scheduler (app/data/scheduler.py). This builder never calls upsert_chunks to
avoid loading the sentence-transformers model on every PDF request.
"""
import logging
from datetime import datetime

from app.data.wfp_loader import fetch_latest_prices
from app.rag.generator import generate_analysis
from app.rag.vector_store import collection_count

logger = logging.getLogger(__name__)


async def build_report_data(month_label=None) -> dict:
    """
    Fast PDF report pipeline:
    1. Fetch latest WFP prices (uses in-memory cache after first load)
    2. Generate LLM analysis (RAG context injected if KB is populated; skipped if empty)
    3. Return structured dict ready for pdf.py

    Vector store indexing is NOT done here — see app/data/scheduler.py.
    """
    now = datetime.now()
    month_label = month_label or now.strftime("%B %Y").capitalize()
    month_id = now.strftime("%Y-%m")

    logger.info(f"[Builder] Starting report build for {month_label}")

    # 1. Prices (cached after first load, usually instantaneous)
    price_data = await fetch_latest_prices()
    prices = price_data.get("prices", [])
    logger.info(f"[Builder] Got {len(prices)} price entries")

    # 2. Knowledge base size (informational only)
    kb_size = collection_count()
    logger.info(f"[Builder] Knowledge base: {kb_size} documents indexed")

    # 3. Generate analysis via LLM (Groq Llama 3.3)
    #    retrieve_context() short-circuits automatically if KB is empty
    result = await generate_analysis(prices=prices, month_label=month_label)

    return {
        "month_label": month_label,
        "month_id": month_id,
        "generated_at": now.strftime("%d/%m/%Y à %H:%M"),
        "prices": prices,
        "price_updated_at": price_data.get("updated_at", ""),
        "gdelt_articles_count": kb_size,
        "analysis_text": result["analysis"],
        "tokens_used": result["tokens_used"],
    }
