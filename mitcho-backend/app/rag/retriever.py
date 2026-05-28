"""
High-level retriever: builds a rich context string from the vector store
for a given analysis query.
"""
import logging

from app.rag.vector_store import query_collection

logger = logging.getLogger(__name__)

ANALYSIS_QUERY = (
    "sécurité alimentaire Bénin prix vivriers maïs riz gari niébé "
    "marché Cotonou Malanville tension alimentaire crise prévision"
)


def retrieve_context(query=None, n_results: int = 10) -> str:
    """
    Returns a formatted context string composed of the top retrieved chunks,
    ready to be injected into the LLM prompt.
    """
    q = query or ANALYSIS_QUERY
    try:
        chunks = query_collection(q, n_results=n_results)
    except Exception as e:
        logger.warning(f"[Retriever] Vector store unavailable: {e}")
        return "Base de connaissances en cours d'initialisation."

    if not chunks:
        return "Aucune donnée contextuelle disponible dans la base de connaissances."

    lines = ["CONTEXTE FACTUEL RÉCENT (sources GDELT + WFP) :\n"]
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source", "inconnu")
        date = chunk["metadata"].get("date", "")
        lines.append(f"[{i}] [{source.upper()} — {date}]\n{chunk['content']}\n")

    context = "\n".join(lines)
    logger.info(f"[Retriever] Built context from {len(chunks)} chunks ({len(context)} chars)")
    return context
