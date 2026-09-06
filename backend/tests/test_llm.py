"""Unit tests for llm.py's provider selection and response parsing.

Mocks httpx.AsyncClient rather than hitting real APIs — these test our
parsing/selection logic, not whether Anthropic/Gemini/Ollama are up.
"""

import pytest

from app.services import llm


class _FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, response_json, captured: dict):
        self._response_json = response_json
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, **kwargs):
        self._captured["url"] = url
        self._captured.update(kwargs)
        return _FakeResponse(self._response_json)


def _patch_client(monkeypatch, response_json):
    captured: dict = {}
    monkeypatch.setattr(
        llm.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(response_json, captured)
    )
    return captured


async def test_call_anthropic_parses_response(monkeypatch):
    captured = _patch_client(
        monkeypatch, {"content": [{"text": "A node that sends a Slack message."}]}
    )
    result = await llm._call_anthropic("some prompt")
    assert result == "A node that sends a Slack message."
    assert captured["url"] == "https://api.anthropic.com/v1/messages"


async def test_call_gemini_parses_response(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm, "GEMINI_MODEL", "gemini-2.0-flash")
    captured = _patch_client(
        monkeypatch,
        {"candidates": [{"content": {"parts": [{"text": "A node that logs the result."}]}}]},
    )
    result = await llm._call_gemini("some prompt")
    assert result == "A node that logs the result."
    assert captured["url"].endswith("/models/gemini-2.0-flash:generateContent")
    assert captured["params"] == {"key": "fake-key"}


async def test_call_ollama_parses_response(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_URL", "http://localhost:11434")
    captured = _patch_client(monkeypatch, {"response": "A node that filters the input."})
    result = await llm._call_ollama("some prompt")
    assert result == "A node that filters the input."
    assert captured["url"] == "http://localhost:11434/api/generate"


@pytest.mark.parametrize(
    "anthropic_key,gemini_key,ollama_url,expected_provider",
    [
        ("key", "key", "url", "anthropic"),
        (None, "key", "url", "gemini"),
        (None, None, "url", "ollama"),
        (None, None, None, "fallback"),
    ],
)
async def test_generate_next_node_spec_provider_precedence(
    monkeypatch, anthropic_key, gemini_key, ollama_url, expected_provider
):
    # Anthropic > Gemini > Ollama > deterministic fallback, in that order —
    # see llm.py's generate_next_node_spec and .env.example.
    monkeypatch.setattr(llm, "ANTHROPIC_API_KEY", anthropic_key)
    monkeypatch.setattr(llm, "GEMINI_API_KEY", gemini_key)
    monkeypatch.setattr(llm, "OLLAMA_URL", ollama_url)

    calls = []
    monkeypatch.setattr(llm, "_call_anthropic", _tracking_stub("anthropic", calls))
    monkeypatch.setattr(llm, "_call_gemini", _tracking_stub("gemini", calls))
    monkeypatch.setattr(llm, "_call_ollama", _tracking_stub("ollama", calls))

    result = await llm.generate_next_node_spec("Webhook", "My Workflow", ["Set", "IF"])

    if expected_provider == "fallback":
        assert calls == []
        assert "Webhook" in result
    else:
        assert calls == [expected_provider]


def _tracking_stub(name, calls):
    async def stub(prompt):
        calls.append(name)
        return f"called {name}"

    return stub
