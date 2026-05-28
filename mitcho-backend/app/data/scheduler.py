"""
Background scheduler — keeps the knowledge base fresh automatically.

Jobs:
- Every 6 hours  : index latest GDELT articles into ChromaDB
- Every 1st of month at 08:00 : generate monthly report + send emails

IMPORTANT: upsert_chunks() is synchronous and loads a heavy sentence-transformers
model. It MUST be called via run_in_executor() to avoid blocking the event loop.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None
_index_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexer")


def _sync_upsert(chunks):
    """Run upsert_chunks synchronously in a dedicated thread."""
    from app.rag.vector_store import upsert_chunks
    return upsert_chunks(chunks)


async def _ingest_gdelt():
    """
    Fetch GDELT articles and index them into ChromaDB.

    Strategy:
      1. If GOOGLE_CLOUD_PROJECT is configured → use BigQuery (full history, no rate limit)
      2. Otherwise → fallback to DOC API (last 7 days, may be rate-limited)
    """
    from app.core.config import settings
    from app.rag.vector_store import collection_count

    logger.info("[Scheduler] GDELT ingestion started")

    try:
        if settings.GOOGLE_CLOUD_PROJECT:
            # ── BigQuery path (preferred) ──────────────────────────────────────
            from app.data.gdelt_bq_loader import (
                fetch_gdelt_bq_articles,
                bq_articles_to_rag_chunks,
            )
            target_month = datetime.now().strftime("%Y-%m")
            articles = await fetch_gdelt_bq_articles(
                project_id=settings.GOOGLE_CLOUD_PROJECT,
                target_month=target_month,
                max_rows=500,
            )
            chunks = bq_articles_to_rag_chunks(articles)
            source_label = f"BigQuery [{target_month}]"
        else:
            # ── DOC API fallback ───────────────────────────────────────────────
            from app.data.gdelt_loader import fetch_gdelt_articles, articles_to_rag_chunks
            articles = await fetch_gdelt_articles(timespan="7d")
            chunks = articles_to_rag_chunks(articles)
            source_label = "DOC API [7d]"

        if chunks:
            loop = asyncio.get_event_loop()
            n = await loop.run_in_executor(_index_executor, _sync_upsert, chunks)
            logger.info(
                f"[Scheduler] GDELT ingestion complete ({source_label}): "
                f"{n} chunks indexed. Total KB: {collection_count()}"
            )
        else:
            logger.info(f"[Scheduler] GDELT ingestion: 0 articles ({source_label})")

    except Exception as exc:
        logger.error(f"[Scheduler] GDELT ingestion failed: {exc}")


async def _ingest_wfp():
    """Fetch latest WFP prices and index the summary chunk (indexing in thread)."""
    try:
        from app.data.wfp_loader import fetch_latest_prices

        logger.info("[Scheduler] WFP price ingestion started")
        data = await fetch_latest_prices()
        if data.get("rag_chunk"):
            month_id = data.get("updated_at", datetime.now().strftime("%Y-%m"))
            chunk = [{
                "doc_id": f"wfp-prices-{month_id}",
                "content": data["rag_chunk"],
                "source": "wfp",
                "metadata": {"source": "wfp", "date": month_id, "type": "prices"},
            }]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_index_executor, _sync_upsert, chunk)
            logger.info(f"[Scheduler] WFP prices indexed for {month_id}")
        else:
            logger.info("[Scheduler] WFP ingestion complete: no chunk to index")
    except Exception as exc:
        logger.error(f"[Scheduler] WFP ingestion failed: {exc}")


async def _generate_monthly_report():
    """Generate monthly analysis report and notify subscribers."""
    try:
        from app.reports.builder import build_report_data
        from app.reports.pdf import generate_pdf
        from app.email.sender import send_monthly_report_notification
        import os

        logger.info("[Scheduler] Monthly report generation started")
        data = await build_report_data()

        # Save PDF to disk
        pdf_bytes = generate_pdf(data)
        month_id = data["month_id"]
        os.makedirs("reports", exist_ok=True)
        pdf_path = f"reports/mitcho-rapport-{month_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"[Scheduler] PDF saved: {pdf_path}")

        # Notify subscribers (fetch from DB)
        from db.database import AsyncSessionLocal
        from db.models import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.is_subscribed == True, User.is_active == True)
            )
            subscribers = [{"email": u.email, "name": u.name} for u in result.scalars().all()]

        summary = _extract_summary(data.get("analysis_text", ""))
        send_monthly_report_notification(subscribers, data["month_label"], summary)

    except Exception as exc:
        logger.error(f"[Scheduler] Monthly report failed: {exc}")


def _extract_summary(analysis_text: str) -> str:
    """Extract the executive summary from the analysis text."""
    lines = analysis_text.split("\n")
    in_summary = False
    summary_lines = []
    for line in lines:
        if "Résumé Exécutif" in line or "résumé exécutif" in line.lower():
            in_summary = True
            continue
        if in_summary:
            if line.startswith("##"):
                break
            if line.strip():
                summary_lines.append(line.strip())
    return " ".join(summary_lines[:5]) or "Rapport mensuel disponible."


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler()

    # GDELT ingestion every 6 hours
    _scheduler.add_job(
        _ingest_gdelt,
        trigger=IntervalTrigger(hours=6),
        id="gdelt_ingestion",
        replace_existing=True,
        name="GDELT Article Ingestion",
    )

    # WFP prices every 24 hours
    _scheduler.add_job(
        _ingest_wfp,
        trigger=IntervalTrigger(hours=24),
        id="wfp_ingestion",
        replace_existing=True,
        name="WFP Price Ingestion",
    )

    # Monthly report on the 1st of each month at 08:00
    _scheduler.add_job(
        _generate_monthly_report,
        trigger=CronTrigger(day=1, hour=8, minute=0),
        id="monthly_report",
        replace_existing=True,
        name="Monthly Report Generation",
    )

    _scheduler.start()
    logger.info("[Scheduler] Started — GDELT every 6h, WFP every 24h, report on 1st of month")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("[Scheduler] Stopped")


# Public aliases for use in main.py startup
ingest_gdelt = _ingest_gdelt
ingest_wfp   = _ingest_wfp
