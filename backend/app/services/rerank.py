from app.models.schemas import Suggestion
from app.services.retrieval import NODE_BY_TYPE

# Chosen by data_pipeline/evaluate.py's weight sweep against 1,599 real
# held-out edges from scraped n8n templates, not guessed. Pure stats
# (semantic_weight=0.0) actually scored best on every metric (MRR, Recall@K)
# there — semantic search's contribution is limited right now because most
# node types still have a placeholder description rather than a real one
# (see README's Known limitations). 0.1 stays just above 0.0 rather than
# literally at it, since a weight of exactly 0.0 degenerates the "unknown
# node type" fallback path to an arbitrary tie-order instead of a true
# similarity ranking. Re-run the sweep after writing more real descriptions —
# this may well change once semantic search has better signal to work with.
STATS_WEIGHT = 0.9
SEMANTIC_WEIGHT = 0.1


def merge_and_rank(
    stats_candidates: list[dict],
    semantic_candidates: list[dict],
    top_k: int,
    stats_weight: float = STATS_WEIGHT,
    semantic_weight: float = SEMANTIC_WEIGHT,
) -> list[Suggestion]:
    """Combine transition-frequency candidates and semantic-search candidates
    into one ranked list. A node appearing in both sources gets boosted
    (source="both") since it's corroborated two different ways.

    stats_weight/semantic_weight default to the module constants but can be
    overridden — see data_pipeline/evaluate.py, which sweeps this split
    against real held-out data rather than trusting the default.
    """
    max_count = max((c["count"] for c in stats_candidates), default=1)

    scored: dict[str, dict] = {}

    for c in stats_candidates:
        node_type = c["to"]
        norm_score = c["count"] / max_count
        scored[node_type] = {
            "score": norm_score * stats_weight,
            "source": "stats",
            "reason": "Frequently follows this node in similar workflows.",
        }

    for c in semantic_candidates:
        node_type = c["node_type"]
        contribution = c["score"] * semantic_weight
        if node_type in scored:
            scored[node_type]["score"] += contribution
            scored[node_type]["source"] = "both"
            scored[node_type]["reason"] = (
                "Commonly follows this node and semantically matches the workflow's intent."
            )
        else:
            scored[node_type] = {
                "score": contribution,
                "source": "semantic",
                "reason": "Semantically matches what this workflow likely needs next.",
            }

    ranked = sorted(scored.items(), key=lambda kv: kv[1]["score"], reverse=True)[:top_k]

    suggestions = []
    for node_type, info in ranked:
        meta = NODE_BY_TYPE.get(node_type)
        if not meta:
            continue
        suggestions.append(
            Suggestion(
                node_type=node_type,
                display_name=meta["display_name"],
                description=meta["description"],
                score=round(info["score"], 4),
                reason=info["reason"],
                source=info["source"],
            )
        )
    return suggestions
