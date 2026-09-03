import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "node_metadata.json"

with open(DATA_PATH, encoding="utf-8") as f:
    NODE_METADATA: list[dict] = json.load(f)

NODE_BY_TYPE: dict[str, dict] = {n["type"]: n for n in NODE_METADATA}

_model = SentenceTransformer("all-MiniLM-L6-v2")

_NODE_TYPES = [n["type"] for n in NODE_METADATA]
_NODE_DOCS = [f"{n['display_name']}: {n['description']}" for n in NODE_METADATA]
_NODE_EMBEDDINGS = _model.encode(_NODE_DOCS, normalize_embeddings=True)


def semantic_search(query: str, top_k: int = 5, exclude: set[str] | None = None) -> list[dict]:
    """Embed `query` and return the top_k most similar nodes by cosine
    similarity (1 = identical, 0 = unrelated). The node corpus here is tiny
    (a few hundred types at most), so brute-force cosine similarity over an
    in-memory matrix is plenty fast — no need for an ANN index/vector DB.
    """
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
