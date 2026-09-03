import json
import logging
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "node_metadata.json"

with open(DATA_PATH, encoding="utf-8") as f:
    NODE_METADATA: list[dict] = json.load(f)

NODE_BY_TYPE: dict[str, dict] = {n["type"]: n for n in NODE_METADATA}

_NODE_TYPES = [n["type"] for n in NODE_METADATA]
_NODE_DOCS = [f"{n['display_name']}: {n['description']}" for n in NODE_METADATA]

# Loaded lazily by `load_model()`, called from the FastAPI startup hook. A
# module-level load would make import time (and therefore test collection)
# depend on downloading model weights; this way the app controls when that
# happens and can report it via /health instead of failing silently.
_model: SentenceTransformer | None = None
_NODE_EMBEDDINGS: np.ndarray | None = None


def load_model() -> bool:
    """Load the sentence-transformer model and embed the node corpus.

    Returns True on success. Returns False (rather than raising) on failure
    so the app can still start and serve stats-only suggestions with
    semantic search degraded — see /health's `model_loaded` field.
    """
    global _model, _NODE_EMBEDDINGS
    try:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _NODE_EMBEDDINGS = _model.encode(_NODE_DOCS, normalize_embeddings=True)
        return True
    except Exception:
        logger.exception("Failed to load semantic search model")
        _model = None
        _NODE_EMBEDDINGS = None
        return False


def is_ready() -> bool:
    return _model is not None


def semantic_search(query: str, top_k: int = 5, exclude: set[str] | None = None) -> list[dict]:
    """Embed `query` and return the top_k most similar nodes by cosine
    similarity (1 = identical, 0 = unrelated). The node corpus here is tiny
    (a few hundred types at most), so brute-force cosine similarity over an
    in-memory matrix is plenty fast — no need for an ANN index/vector DB.

    Returns an empty list if the model failed to load — callers still get
    stats-based suggestions in that case, just no semantic ones.
    """
    if _model is None:
        return []
    exclude = exclude or set()
    query_vec = _model.encode([query], normalize_embeddings=True)[0]
    similarities = _NODE_EMBEDDINGS @ query_vec  # cosine similarity since both normalized

    ranked_indices = np.argsort(-similarities)

    hits = []
    for idx in ranked_indices:
        node_type = _NODE_TYPES[idx]
        if node_type in exclude:
            continue
        meta = NODE_BY_TYPE[node_type]
        hits.append(
            {
                "node_type": node_type,
                "display_name": meta["display_name"],
                "description": meta["description"],
                "score": round(float(similarities[idx]), 4),
            }
        )
        if len(hits) >= top_k:
            break
    return hits
