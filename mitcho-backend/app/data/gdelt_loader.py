"""
Fetches recent news articles from the GDELT 2.0 Doc API related to
food security in Benin and West Africa.

GDELT API is free, no API key required, updated every 15 minutes.
Docs: https://blog.gdeltproject.org/gdelt-2-0-our-global-database-of-society/
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

QUERIES = [
    '"Benin" food price market',
    '"Benin" food security crisis',
    '"Benin" agriculture harvest',
    '"West Africa" food prices 2026',
    '"Malanville" OR "Cotonou" market',
    '"Benin" cereal maize rice',
]

TIMESPAN_OPTIONS = {
    "7d":  "LAST7DAYS",
    "30d": "LAST30DAYS",
    "90d": "LAST3MONTHS",
}


def _make_doc_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


async def fetch_gdelt_articles(timespan: str = "30d", max_per_query=None) -> list[dict]:
    """
    Fetches and deduplicates GDELT articles across all queries.

    Returns a list of dicts:
        { doc_id, title, url, published_at, tone, themes, source_country, snippet }
    """
    max_records = max_per_query or settings.GDELT_MAX_RECORDS
    ts = TIMESPAN_OPTIONS.get(timespan, "LAST30DAYS")

    seen_ids: set[str] = set()
    articles: list[dict] = []

    async with httpx.AsyncClient(timeout=20) as client:
        for i, query in enumerate(QUERIES):
            # Respect GDELT rate limits — pause between requests
            if i > 0:
                await asyncio.sleep(3)

            try:
                resp = await client.get(
                    GDELT_DOC_API,
                    params={
                        "query": query,
                        "mode": "artlist",
                        "maxrecords": max_records,
                        "timespan": ts,
                        "format": "json",
                        "sourcelang": "French,English",
                    },
                )
                if resp.status_code == 429:
                    logger.warning(f"[GDELT] Rate limited — waiting 10s before next query")
                    await asyncio.sleep(10)
                    continue
                if resp.status_code != 200:
                    logger.warning(f"[GDELT] HTTP {resp.status_code} for query: {query}")
                    continue

                # GDELT returns empty body when there are no results
                body = resp.text.strip()
                if not body:
                    logger.info(f"[GDELT] No results (empty body) for: {query}")
                    continue
                try:
                    data = resp.json()
                except Exception:
                    logger.info(f"[GDELT] Non-JSON response for: {query}")
                    continue
                raw_articles = data.get("articles") or []

                for art in raw_articles:
                    url = art.get("url", "")
                    if not url:
                        continue
                    doc_id = _make_doc_id(url)
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)

                    # Parse date
                    raw_date = art.get("seendate", "")
                    published_at = None
                    try:
                        published_at = datetime.strptime(raw_date, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=timezone.utc
                        )
                    except Exception:
                        pass

                    articles.append({
                        "doc_id": doc_id,
                        "title": art.get("title", "").strip(),
                        "url": url,
                        "published_at": published_at,
                        "tone": art.get("tone", 0.0),
                        "domain": art.get("domain", ""),
                        "language": art.get("language", ""),
                        "source_country": art.get("sourcecountry", ""),
                    })

            except Exception as exc:
                logger.warning(f"[GDELT] Query failed: {query!r} — {exc}")
                continue

    logger.info(f"[GDELT] Fetched {len(articles)} unique articles")
    return articles


def articles_to_rag_chunks(articles: list[dict]) -> list[dict]:
    """
    Converts GDELT articles into text chunks suitable for embedding.
    Each chunk = one article (title + metadata).

    Returns: [{ doc_id, content, metadata }]
    """
    chunks = []
    for art in articles:
        date_str = art["published_at"].strftime("%d/%m/%Y") if art["published_at"] else "date inconnue"
        tone_label = _tone_label(art.get("tone", 0))

        content = (
            f"[Source GDELT — {date_str}] {art['title']}\n"
            f"Domaine: {art['domain']} | Langue: {art['language']} | "
            f"Pays source: {art['source_country']} | Tonalité: {tone_label}\n"
            f"URL: {art['url']}"
        )

        chunks.append({
            "doc_id": art["doc_id"],
            "content": content,
            "source": "gdelt",
            "title": art["title"],
            "url": art["url"],
            "published_at": art["published_at"],
            "metadata": {
                "source": "gdelt",
                "domain": art["domain"],
                "tone": str(art.get("tone", 0)),
                "date": date_str,
            },
        })
    return chunks


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
