from app.services import rerank


def test_node_in_both_sources_is_marked_and_boosted():
    stats_candidates = [{"to": "n8n-nodes-base.if", "count": 10}]
    semantic_candidates = [{"node_type": "n8n-nodes-base.if", "score": 0.9}]

    suggestions = rerank.merge_and_rank(stats_candidates, semantic_candidates, top_k=5)

    assert len(suggestions) == 1
    assert suggestions[0].source == "both"
    # 1.0 (only stats candidate, so normalized count = 1) * 0.6 + 0.9 * 0.4
    expected = 1.0 * rerank.STATS_WEIGHT + 0.9 * rerank.SEMANTIC_WEIGHT
    assert suggestions[0].score == round(expected, 4)


def test_stats_only_and_semantic_only_candidates_both_included():
    stats_candidates = [{"to": "n8n-nodes-base.if", "count": 5}]
    semantic_candidates = [{"node_type": "n8n-nodes-base.slack", "score": 0.8}]

    suggestions = rerank.merge_and_rank(stats_candidates, semantic_candidates, top_k=5)

    sources = {s.node_type: s.source for s in suggestions}
    assert sources["n8n-nodes-base.if"] == "stats"
    assert sources["n8n-nodes-base.slack"] == "semantic"


def test_respects_top_k():
    stats_candidates = [
        {"to": "n8n-nodes-base.if", "count": 10},
        {"to": "n8n-nodes-base.set", "count": 8},
        {"to": "n8n-nodes-base.switch", "count": 5},
    ]
    suggestions = rerank.merge_and_rank(stats_candidates, [], top_k=2)
    assert len(suggestions) == 2


def test_unknown_node_type_is_dropped_silently():
    stats_candidates = [{"to": "n8n-nodes-base.notARealNode", "count": 10}]
    suggestions = rerank.merge_and_rank(stats_candidates, [], top_k=5)
    assert suggestions == []
