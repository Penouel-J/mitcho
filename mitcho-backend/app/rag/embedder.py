"""
Embedding layer with two backends:
  1. sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) — best quality,
     works in French AND English, no GPU required.
  2. ChromaDB built-in (all-MiniLM-L6-v2) — fallback if sentence-transformers
     is not installed yet.
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_USE_SENTENCE_TRANSFORMERS = None  # type: ignore[assignment]


def _check_sentence_transformers() -> bool:
    global _USE_SENTENCE_TRANSFORMERS
    if _USE_SENTENCE_TRANSFORMERS is None:
        # Respect de la variable d'environnement (Render free tier = false)
        from app.core.config import settings
        if not settings.use_sentence_transformers:
            logger.info("[Embedder] USE_SENTENCE_TRANSFORMERS=false — using ChromaDB ONNX embeddings")
            _USE_SENTENCE_TRANSFORMERS = False
            return False
        try:
            import sentence_transformers  # noqa: F401
            _USE_SENTENCE_TRANSFORMERS = True
        except ImportError:
            _USE_SENTENCE_TRANSFORMERS = False
            logger.warning("[Embedder] sentence-transformers non disponible — fallback ChromaDB ONNX")
    return _USE_SENTENCE_TRANSFORMERS


@lru_cache(maxsize=1)
def _get_st_model():
    from sentence_transformers import SentenceTransformer
    logger.info(f"[Embedder] Loading sentence-transformers model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    logger.info("[Embedder] Model ready")
    return model


@lru_cache(maxsize=1)
def _get_chroma_ef():
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    logger.info("[Embedder] Using ChromaDB default embedding function")
    return DefaultEmbeddingFunction()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if _check_sentence_transformers():
        model = _get_st_model()
        return model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()
    else:
        ef = _get_chroma_ef()
        return [list(e) for e in ef(texts)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
