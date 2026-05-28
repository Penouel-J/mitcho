"""
MITCHÔ Backend — FastAPI entry point.

Start with:
    uvicorn main:app --reload --port 8000

Interactive API docs:
    http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api import auth, prices, analysis, report
from db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mitcho")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("MITCHÔ backend starting up...")
    await init_db()
    logger.info("Database initialized")

    # Start background scheduler (GDELT + WFP ingestion, monthly reports)
    from app.data.scheduler import start_scheduler
    start_scheduler()

    # Kick off initial GDELT ingestion on first run
    from app.rag.vector_store import collection_count
    from app.data.scheduler import ingest_wfp, ingest_gdelt
    if collection_count() == 0:
        logger.info("Knowledge base is empty — starting background ingestion...")
        import asyncio
        asyncio.create_task(ingest_wfp())
        asyncio.create_task(ingest_gdelt())

    yield

    # Shutdown
    from app.data.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("MITCHÔ backend shut down")


app = FastAPI(
    title="MITCHÔ API",
    description="Intelligence Publique pour la Sécurité Alimentaire au Bénin",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development (file://, localhost variants)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router)
app.include_router(prices.router)
app.include_router(analysis.router)
app.include_router(report.router)

# Serve generated PDF reports as static files
import os
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "MITCHÔ API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    from app.rag.vector_store import collection_count
    return {
        "status": "ok",
        "knowledge_base_docs": collection_count(),
    }
