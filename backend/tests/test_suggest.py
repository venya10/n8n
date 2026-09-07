from app.routes import suggest as suggest_route
from app.services import stats


def _suggest(client, **overrides):
    body = {
        "context": {
            "nodes": [{"id": "1", "type": "n8n-nodes-base.webhook"}],
            "last_node_id": "1",
        },
        "top_k": 5,
        "use_llm": False,
    }
    body.update(overrides)
    return client.post("/suggest", json=body)


def test_suggest_known_node_returns_ranked_suggestions(client):
    res = _suggest(client)
    assert res.status_code == 200
    body = res.json()

    suggestions = body["suggestions"]
    assert len(suggestions) > 0
    # Whatever the mined transition data currently says most often follows a
    # webhook should show up in the ranked suggestions. Reading it from
    # stats.py directly (rather than hardcoding a node type) keeps this test
    # valid across dataset regenerations.
    top_stats_candidate = stats.get_common_next_nodes("n8n-nodes-base.webhook", limit=1)[0]["to"]
    assert any(s["node_type"] == top_stats_candidate for s in suggestions)
    # Scores are sorted descending.
    scores = [s["score"] for s in suggestions]
    assert scores == sorted(scores, reverse=True)
    assert body["generated_spec"] is None


def test_suggest_excludes_nodes_already_in_workflow(client):
    body = {
        "context": {
            "nodes": [
                {"id": "1", "type": "n8n-nodes-base.webhook"},
                {"id": "2", "type": "n8n-nodes-base.if"},
            ],
            "last_node_id": "1",
        },
        "top_k": 5,
        "use_llm": False,
    }
    res = client.post("/suggest", json=body)
    assert res.status_code == 200
    types = [s["node_type"] for s in res.json()["suggestions"]]
    assert "n8n-nodes-base.if" not in types


def test_suggest_unknown_node_type_falls_back_to_semantic_only(client):
    res = _suggest(
        client,
        context={
            "nodes": [{"id": "1", "type": "n8n-nodes-base.totallyMadeUpNode"}],
            "last_node_id": "1",
        },
    )
    assert res.status_code == 200
    suggestions = res.json()["suggestions"]
    assert all(s["source"] == "semantic" for s in suggestions)


def test_suggest_requires_at_least_one_node(client):
    res = _suggest(client, context={"nodes": [], "last_node_id": None})
    assert res.status_code == 400


def test_suggest_uses_llm_fallback_spec_when_use_llm_true(client):
    # No ANTHROPIC_API_KEY / OLLAMA_URL configured in the test environment,
    # so this exercises llm.py's deterministic fallback path.
    res = _suggest(client, use_llm=True)
    assert res.status_code == 200
    assert res.json()["generated_spec"] is not None


async def test_suggest_passes_other_workflow_nodes_to_llm(client, monkeypatch):
    captured = {}

    async def fake_generate_next_node_spec(last_node_name, workflow_name, common_next, other_nodes):
        captured["last_node_name"] = last_node_name
        captured["other_nodes"] = other_nodes
        return "a fake generated spec"

    monkeypatch.setattr(
        suggest_route.llm, "generate_next_node_spec", fake_generate_next_node_spec
    )

    body = {
        "context": {
            "nodes": [
                {"id": "1", "type": "n8n-nodes-base.manualTrigger"},
                {"id": "2", "type": "n8n-nodes-base.set"},
                {"id": "3", "type": "n8n-nodes-base.webhook"},
            ],
            "last_node_id": "3",
        },
        "top_k": 5,
        "use_llm": True,
    }
    res = client.post("/suggest", json=body)

    assert res.status_code == 200
    assert res.json()["generated_spec"] == "a fake generated spec"
    # The last node (Webhook, id "3") is excluded — it's conveyed separately
    # as last_node_name — but the other two nodes already in the workflow
    # should be passed through, not just silently dropped.
    assert captured["last_node_name"] == "Webhook"
    assert set(captured["other_nodes"]) == {"Manual Trigger", "Edit Fields (Set)"}
