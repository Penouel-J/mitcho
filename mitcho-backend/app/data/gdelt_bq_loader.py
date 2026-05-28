"""
GDELT 2.0 data loader via Google BigQuery.

Dataset: gdelt-bq.gdeltv2.gkg (Global Knowledge Graph)
- Publicly accessible, partitioned by date
- Updated every 15 minutes, history since Feb 2015
- No rate limits (unlike the DOC API)

Prerequisites:
  1. Google Cloud project with BigQuery API enabled
  2. GOOGLE_APPLICATION_CREDENTIALS pointing to a service account JSON
     OR gcloud CLI authenticated (gcloud auth application-default login)
  3. Set GOOGLE_CLOUD_PROJECT in .env

Cost: ~0 for filtered queries (partitioned by date, Benin is a small country).
Free tier: 1 TB/month. A 1-month Benin food query scans ~5-20 GB.
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── GDELT GKG Theme codes related to food security ────────────────────────────
FOOD_THEMES = [
    "FOOD_PRICES",
    "FOOD_INSECURITY",
    "FOOD_SECURITY",
    "FAMINE",
    "WFP",
    "SOC_AGRICULTURAL",
    "ECON_FOODPRICES",
    "AGRICULTURE",
    "CEREAL",
    "LIVESTOCK",
    "CROP_FAILURE",
    "DROUGHT",
    "FLOODING",
]

# West Africa + Benin neighbors — broader context for regional signals
LOCATION_KEYWORDS = [
    "benin",
    "cotonou",
    "malanville",
    "parakou",
    "west africa",
    "afrique ouest",
    "niger",
    "burkina",
    "togo",
]


def _build_query(start_date: str, end_date: str, max_rows: int = 500) -> str:
    """
    Build a BigQuery SQL query against gdelt-bq.gdeltv2.gkg.

    start_date / end_date: "YYYY-MM-DD" format
    Uses _PARTITIONTIME to minimize data scanned (cost control).
    """
    theme_conditions = " OR ".join(
        [f"UPPER(Themes) LIKE '%{t}%'" for t in FOOD_THEMES]
    )
    location_conditions = " OR ".join(
        [f"LOWER(Locations) LIKE '%{kw}%'" for kw in LOCATION_KEYWORDS]
    )

    return f"""
SELECT
    DATE,
    SourceCommonName,
    DocumentIdentifier,
    Themes,
    Locations,
    Tone,
    TranslationInfo
FROM `gdelt-bq.gdeltv2.gkg`
WHERE
    _PARTITIONTIME >= TIMESTAMP('{start_date}')
    AND _PARTITIONTIME < TIMESTAMP('{end_date}')
    AND ({theme_conditions})
    AND ({location_conditions})
ORDER BY DATE DESC
LIMIT {max_rows}
"""


def _parse_tone(tone_str: str) -> float:
    """Extract overall tone score from GDELT tone field (first value)."""
    try:
        return float(tone_str.split(",")[0])
    except Exception:
        return 0.0


def _tone_label(tone: float) -> str:
    if tone < -5:
        return "très négatif"
    if tone < -1:
        return "négatif"
    if tone > 5:
        return "très positif"
    if tone > 1:
        return "positif"
    return "neutre"


def _doc_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse GDELT DATE field: YYYYMMDDHHMMSS"""
    try:
        return datetime.strptime(str(date_str)[:14], "%Y%m%d%H%M%S")
    except Exception:
        return None


async def fetch_gdelt_bq_articles(
    project_id: str,
    target_month: Optional[str] = None,
    months_back: int = 1,
    max_rows: int = 500,
) -> list[dict]:
    """
    Fetch GDELT articles from BigQuery for a specific month or recent period.

    Args:
        project_id: Google Cloud project ID (for billing)
        target_month: "YYYY-MM" — if provided, fetches that specific month
        months_back: if target_month is None, fetches the last N months
        max_rows: max articles to return

    Returns: list of article dicts with doc_id, title, url, published_at, tone, themes
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        logger.error(
            "[GDELT BQ] google-cloud-bigquery not installed. "
            "Run: pip install google-cloud-bigquery"
        )
        return []

    # Determine date range
    if target_month:
        try:
            start_dt = datetime.strptime(target_month, "%Y-%m")
            # End = first day of next month
            if start_dt.month == 12:
                end_dt = datetime(start_dt.year + 1, 1, 1)
            else:
                end_dt = datetime(start_dt.year, start_dt.month + 1, 1)
        except ValueError:
            logger.error(f"[GDELT BQ] Invalid target_month format: {target_month}. Use YYYY-MM.")
            return []
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=30 * months_back)

    start_str = start_dt.strftime("%Y-%m-%d")
    end_str   = end_dt.strftime("%Y-%m-%d")

    logger.info(f"[GDELT BQ] Querying {start_str} → {end_str} (project={project_id})")

    try:
        client = bigquery.Client(project=project_id)
        query  = _build_query(start_str, end_str, max_rows)

        query_job = client.query(query)
        rows = list(query_job.result())

        logger.info(f"[GDELT BQ] Query complete — {len(rows)} rows returned")

        articles = []
        seen_ids: set[str] = set()

        for row in rows:
            url = row.DocumentIdentifier or ""
            if not url:
                continue
            doc_id = _doc_id(url)
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)

            tone  = _parse_tone(row.Tone or "")
            published_at = _parse_date(str(row.DATE))

            # Extract a readable title from themes + source
            themes_raw = row.Themes or ""
            theme_list = [t for t in themes_raw.split(";") if t.strip()][:5]
            title = f"[{row.SourceCommonName}] {' | '.join(theme_list[:3])}" if theme_list else row.SourceCommonName

            articles.append({
                "doc_id":       doc_id,
                "title":        title,
                "url":          url,
                "published_at": published_at,
                "tone":         tone,
                "themes":       theme_list,
                "source":       row.SourceCommonName or "",
                "language":     "en" if not row.TranslationInfo else "fr",
            })

        logger.info(f"[GDELT BQ] {len(articles)} unique articles after dedup")
        return articles

    except Exception as exc:
        logger.error(f"[GDELT BQ] Query failed: {exc}")
        return []


def bq_articles_to_rag_chunks(articles: list[dict]) -> list[dict]:
    """Convert BQ article list to RAG-ready chunks for ChromaDB."""
    chunks = []
    for art in articles:
        date_str    = art["published_at"].strftime("%d/%m/%Y") if art["published_at"] else "date inconnue"
        tone_label  = _tone_label(art.get("tone", 0))
        themes_text = ", ".join(art.get("themes", [])[:5])

        content = (
            f"[GDELT BigQuery — {date_str}] {art['title']}\n"
            f"Source: {art['source']} | Tonalité: {tone_label}\n"
            f"Thèmes: {themes_text}\n"
            f"URL: {art['url']}"
        )

        chunks.append({
            "doc_id":      art["doc_id"],
            "content":     content,
            "source":      "gdelt_bq",
            "title":       art["title"],
            "url":         art["url"],
            "published_at": art["published_at"],
            "metadata": {
                "source":  "gdelt_bq",
                "themes":  themes_text,
                "tone":    str(art.get("tone", 0)),
                "date":    date_str,
            },
        })
    return chunks


async def ingest_month(project_id: str, target_month: str) -> int:
    """
    One-shot ingestion: fetch GDELT data for a specific month and index into ChromaDB.

    Args:
        project_id: Google Cloud project ID
        target_month: "YYYY-MM" (ex: "2026-05")

    Returns: number of chunks indexed
    """
    from app.rag.vector_store import upsert_chunks

    articles = await fetch_gdelt_bq_articles(
        project_id=project_id,
        target_month=target_month,
        max_rows=500,
    )
    if not articles:
        logger.warning(f"[GDELT BQ] No articles for {target_month}")
        return 0

    chunks = bq_articles_to_rag_chunks(articles)
    n = upsert_chunks(chunks)
    logger.info(f"[GDELT BQ] Indexed {n} chunks for {target_month}")
    return n
