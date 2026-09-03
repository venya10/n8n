from app.services import stats


def test_get_common_next_nodes_sorted_by_count_desc():
    results = stats.get_common_next_nodes("n8n-nodes-base.webhook", limit=10)
    counts = [r["count"] for r in results]
    assert counts == sorted(counts, reverse=True)


def test_get_common_next_nodes_respects_limit():
    results = stats.get_common_next_nodes("n8n-nodes-base.webhook", limit=2)
    assert len(results) <= 2


def test_get_common_next_nodes_unseen_type_returns_empty():
    assert stats.get_common_next_nodes("n8n-nodes-base.doesNotExist") == []


def test_record_feedback_adds_new_edge_for_unseen_pair():
    stats.record_feedback("n8n-nodes-base.doesNotExist", "n8n-nodes-base.if", accepted=True)
    results = stats.get_common_next_nodes("n8n-nodes-base.doesNotExist")
    assert results == [{"to": "n8n-nodes-base.if", "count": 1}]
