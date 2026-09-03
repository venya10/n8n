from app.services import stats


def test_feedback_accepted_reinforces_transition(client):
    before = stats.get_common_next_nodes("n8n-nodes-base.set", limit=50)
    before_count = next((c["count"] for c in before if c["to"] == "n8n-nodes-base.if"), 0)

    res = client.post(
        "/feedback",
        json={
            "from_node_type": "n8n-nodes-base.set",
            "suggested_node_type": "n8n-nodes-base.if",
            "accepted": True,
        },
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    after = stats.get_common_next_nodes("n8n-nodes-base.set", limit=50)
    after_count = next(c["count"] for c in after if c["to"] == "n8n-nodes-base.if")
    assert after_count == before_count + 1


def test_feedback_rejected_is_a_noop(client):
    before = stats.get_common_next_nodes("n8n-nodes-base.webhook", limit=50)

    res = client.post(
        "/feedback",
        json={
            "from_node_type": "n8n-nodes-base.webhook",
            "suggested_node_type": "n8n-nodes-base.if",
            "accepted": False,
        },
    )
    assert res.status_code == 200

    after = stats.get_common_next_nodes("n8n-nodes-base.webhook", limit=50)
    assert before == after
