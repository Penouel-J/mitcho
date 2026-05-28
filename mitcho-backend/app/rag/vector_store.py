"""
ChromaDB persistent vector store for MITCHÔ knowledge base.
Handles indexing and querying of GDELT articles and WFP price data.
"""
import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_collection():
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"[VectorStore] Collection '{settings.CHROMA_COLLECTION}' ready — {collection.count()} docs")
    return collection


def upsert_chunks(chunks: list[dict]) -> int:
    """
    Upserts text chunks into ChromaDB.
    Each chunk must have: doc_id, content, metadata (dict of str→str).
    Returns number of chunks upserted.
    """
    from app.rag.embedder import embed_texts

    if not chunks:
        return 0

    ids = [c["doc_id"] for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]
    embeddings = embed_texts(documents)

    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    logger.info(f"[VectorStore] Upserted {len(chunks)} chunks")
    return len(chunks)


def query_collection(query_text: str, n_results: int = 8, where=None) -> list[dict]:
    """
    Retrieves the top-N most relevant chunks for a given query.
    Returns: [{ id, content, metadata, distance }]
    Short-circuits if collection is empty (avoids loading the embedder unnecessarily).
    """
    collection = get_collection()
    total = collection.count()
    if total == 0:
        logger.info("[VectorStore] Collection is empty — skipping query")
        return []

    from app.rag.embedder import embed_query

    n_results = min(n_results, total)
    query_embedding = embed_query(query_text)

    kwargs: dict = dict(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    return [
        {"id": results["ids"][0][i], "content": docs[i], "metadata": metas[i], "distance": dists[i]}
        for i in range(len(docs))
    ]


def collection_count() -> int:
    return get_collection().count()
