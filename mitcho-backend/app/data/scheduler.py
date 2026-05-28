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
    Ingestion GDELT en deux temps :
      1. Données historiques CSV (2020-2026) — une seule fois au démarrage via ingest_gdelt_csv()
      2. Données récentes DOC API (7 derniers jours) — toutes les 6h

    Cette fonction gère uniquement le rafraîchissement DOC API.
    L'ingestion initiale du CSV est déclenchée séparément (voir ingest_gdelt_csv).
    """
    from app.rag.vector_store import collection_count

    logger.info("[Scheduler] GDELT DOC API refresh démarré")
    try:
        from app.data.gdelt_loader import fetch_gdelt_articles, articles_to_rag_chunks
        articles = await fetch_gdelt_articles(timespan="7d")
        chunks = articles_to_rag_chunks(articles)
        if chunks:
            loop = asyncio.get_event_loop()
            n = await loop.run_in_executor(_index_executor, _sync_upsert, chunks)
            logger.info(f"[Scheduler] DOC API: {n} chunks indexés. Total: {collection_count()}")
        else:
            logger.info("[Scheduler] DOC API: 0 articles trouvés")
    except Exception as exc:
        logger.error(f"[Scheduler] GDELT DOC API échoué: {exc}")


async def ingest_gdelt_csv():
    """
    Ingestion initiale des données historiques GDELT depuis le fichier CSV local.
    Doit être appelé une fois au démarrage si la base vectorielle est vide.
    Fonctionne en arrière-plan (executor) car le chargement CSV est synchrone.
    """
    from app.rag.vector_store import collection_count

    logger.info("[Startup] Ingestion CSV GDELT historique démarrée...")
    try:
        def _sync_load_and_upsert():
            from app.data.gdelt_csv_loader import load_gdelt_csv_chunks
            from app.rag.vector_store import upsert_chunks
            chunks = load_gdelt_csv_chunks()
            if not chunks:
                return 0
            return upsert_chunks(chunks)

        loop = asyncio.get_event_loop()
        n = await loop.run_in_executor(_index_executor, _sync_load_and_upsert)
        total = collection_count()
        logger.info(f"[Startup] CSV GDELT : {n} chunks indexés. Total base: {total}")
        return n
    except Exception as exc:
        logger.error(f"[Startup] Ingestion CSV GDELT échouée: {exc}")
        return 0


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
