from app.models.schemas import Suggestion
from app.services.retrieval import NODE_BY_TYPE

STATS_WEIGHT = 0.6
SEMANTIC_WEIGHT = 0.4


def merge_and_rank(
    stats_candidates: list[dict],
    semantic_candidates: list[dict],
    top_k: int,
) -> list[Suggestion]:
    """Combine transition-frequency candidates and semantic-search candidates
    into one ranked list. A node appearing in both sources gets boosted
    (source="both") since it's corroborated two different ways.
    """
    max_count = max((c["count"] for c in stats_candidates), default=1)

    scored: dict[str, dict] = {}

    for c in stats_candidates:
        node_type = c["to"]
        norm_score = c["count"] / max_count
        scored[node_type] = {
            "score": norm_score * STATS_WEIGHT,
            "source": "stats",
            "reason": "Frequently follows this node in similar workflows.",
        }

    for c in semantic_candidates:
        node_type = c["node_type"]
        contribution = c["score"] * SEMANTIC_WEIGHT
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
