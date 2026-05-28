"""
Fetches the latest WFP food prices for Benin from the HDX dataset.
Returns a list of price records and a formatted text chunk for the RAG pipeline.
"""
import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial

import httpx
import pandas as pd

_thread_pool = ThreadPoolExecutor(max_workers=2)

from app.core.config import settings

logger = logging.getLogger(__name__)

HDX_API_BASE = "https://data.humdata.org/api/3/action"
HDX_DATASET_ID = "wfp-food-prices-for-benin"

# Simple in-memory cache — TTL 6 hours
_prices_cache = None
_prices_cache_time: float = 0.0
CACHE_TTL_SECONDS = 6 * 3600

PRODUCTS_OF_INTEREST = {
    "Maize (white)": "Maïs blanc",
    "Rice (imported)": "Riz importé",
    "Gari": "Gari blanc",
    "Beans (white)": "Niébé blanc",
    "Sorghum": "Sorgho",
    "Millet": "Mil",
    "Cassava": "Manioc",
}

MARKETS_PRIORITY = ["Dantokpa", "Cotonou", "Malanville", "Parakou", "Bohicon"]


async def fetch_wfp_csv_url():
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{HDX_API_BASE}/package_show",
            params={"id": HDX_DATASET_ID},
        )
        resp.raise_for_status()
        data = resp.json()
        resources = data.get("result", {}).get("resources", [])
        for r in resources:
            url = r.get("download_url", "") or r.get("url", "")
            if url.endswith(".csv"):
                return url
    return None


LOCAL_CSV_PATHS = [
    "../prix_vivriers_benin_region_2020_2026.csv",
    "../../prix_vivriers_benin_region_2020_2026.csv",
]


async def fetch_latest_prices(force_refresh: bool = False) -> dict:
    """
    Returns:
        {
          "updated_at": "2026-05",
          "prices": [{"product": str, "market": str, "price": float, "unit": str, "currency": str}, ...]
          "rag_chunk": str   # formatted text ready for embedding
        }

    Strategy:
    1. Return cached result if fresh (< 6h)
    2. Try local CSV (fast, reliable, always available)
    3. Only if local CSV not found, try live HDX/S3 fetch
    """
    global _prices_cache, _prices_cache_time
    import time
    if not force_refresh and _prices_cache and (time.time() - _prices_cache_time) < CACHE_TTL_SECONDS:
        return _prices_cache

    # Try local CSV first — it's fast and reliable
    local = await _load_local_csv_fallback()
    if local:
        _prices_cache = local
        _prices_cache_time = time.time()
        return local

    # No local CSV — try live HDX/S3 (slow, may fail)
    try:
        csv_url = await fetch_wfp_csv_url()
        if not csv_url:
            raise ValueError("CSV URL not found in HDX dataset")

        raw = None
        # Try following the redirect with extended timeout and SSL fallback
        for verify_ssl in (True, False):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0, connect=15.0),
                    follow_redirects=True,
                    verify=verify_ssl,
                ) as client:
                    resp = await client.get(csv_url)
                    resp.raise_for_status()
                    raw = resp.text
                    break
            except Exception as e:
                logger.debug(f"[WFP] Attempt (verify={verify_ssl}) failed: {e}")
                continue

        if raw is None:
            raise ValueError("Could not download WFP CSV after retries")

        # Parse CSV in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(_thread_pool, pd.read_csv, io.StringIO(raw))
        df.columns = [c.strip().lower() for c in df.columns]

        # Normalize column names across WFP CSV variants
        col_map = {
            "adm0_name": "country", "market": "market", "cm_name": "product",
            "mp_price": "price", "um_name": "unit", "cur_name": "currency",
            "mp_year": "year", "mp_month": "month",
            "date": "date", "price": "price",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Build date column if separate year/month exist
        if "date" not in df.columns and "year" in df.columns and "month" in df.columns:
            df["date"] = pd.to_datetime(
                df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2),
                errors="coerce",
            )
        else:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        df = df.dropna(subset=["date", "price"])
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["price"])

        latest_month = df["date"].max().strftime("%Y-%m")

        results = []
        lines = [f"Prix vivriers au Bénin — {latest_month}\n"]

        for raw_name, fr_name in PRODUCTS_OF_INTEREST.items():
            mask = df["product"].str.contains(raw_name, case=False, na=False)
            sub = df[mask].copy()
            if sub.empty:
                continue

            sub_latest = sub[sub["date"] == sub["date"].max()]

            # Prefer priority markets
            chosen = None
            for market in MARKETS_PRIORITY:
                row = sub_latest[sub_latest["market"].str.contains(market, case=False, na=False)]
                if not row.empty:
                    chosen = row.iloc[0]
                    break
            if chosen is None and not sub_latest.empty:
                chosen = sub_latest.iloc[0]

            if chosen is not None:
                price = round(float(chosen["price"]), 0)
                unit = chosen.get("unit", "kg") if "unit" in chosen.index else "kg"
                currency = chosen.get("currency", "XOF") if "currency" in chosen.index else "XOF"
                market_name = chosen.get("market", "Bénin")

                results.append({
                    "product": fr_name,
                    "raw_product": raw_name,
                    "market": market_name,
                    "price": price,
                    "unit": unit,
                    "currency": currency,
                    "month": latest_month,
                })
                lines.append(
                    f"- {fr_name} : {price:,.0f} {currency}/{unit} à {market_name}"
                )

        rag_chunk = "\n".join(lines)
        result = {"updated_at": latest_month, "prices": results, "rag_chunk": rag_chunk}
        _prices_cache = result
        _prices_cache_time = time.time()
        return result

    except Exception as exc:
        logger.warning(f"[WFP] Live fetch failed: {exc} — trying local CSV fallback")
        fallback = await _load_local_csv_fallback()
        if fallback.get("prices"):
            _prices_cache = fallback
            _prices_cache_time = time.time()
        return fallback


async def _load_local_csv_fallback() -> dict:
    """Load prices from the local CSV file included in the project."""
    import os
    loop = asyncio.get_event_loop()
    for path in LOCAL_CSV_PATHS:
        if os.path.exists(path):
            try:
                df = await loop.run_in_executor(_thread_pool, pd.read_csv, path)
                logger.info(f"[WFP] Loaded local fallback CSV: {path}")
                return _parse_local_df(df)
            except Exception as e:
                logger.warning(f"[WFP] Local CSV parse error: {e}")
    logger.warning("[WFP] No local CSV found either — using empty prices")
    return {"updated_at": None, "prices": [], "rag_chunk": ""}


def _parse_local_df(df: pd.DataFrame) -> dict:
    """Parse the local prix_vivriers_benin_region_2020_2026.csv format."""
    df.columns = [c.strip().lower() for c in df.columns]
    # Detect date column
    date_col = next((c for c in df.columns if "date" in c or "mois" in c or "month" in c), None)
    price_col = next((c for c in df.columns if "prix" in c or "price" in c), None)
    product_col = next((c for c in df.columns if "produit" in c or "product" in c or "commodity" in c), None)
    market_col = next((c for c in df.columns if "marché" in c or "market" in c or "place" in c), None)

    if not all([date_col, price_col, product_col]):
        return {"updated_at": None, "prices": [], "rag_chunk": ""}

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=[date_col, price_col])

    latest_date = df[date_col].max()
    latest_month = latest_date.strftime("%Y-%m")
    df_latest = df[df[date_col] == latest_date]

    results = []
    lines = [f"Prix vivriers au Bénin — {latest_month} (source locale)\n"]
    for _, row in df_latest.iterrows():
        product = str(row.get(product_col, ""))
        price = float(row[price_col])
        market = str(row.get(market_col, "Bénin")) if market_col else "Bénin"
        results.append({
            "product": product, "raw_product": product,
            "market": market, "price": round(price, 0),
            "unit": "kg", "currency": "XOF", "month": latest_month,
        })
        lines.append(f"- {product} : {price:,.0f} XOF/kg à {market}")

    return {"updated_at": latest_month, "prices": results, "rag_chunk": "\n".join(lines)}
