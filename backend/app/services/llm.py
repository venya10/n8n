"""HyDE-style "next node spec" generation.

Given the current workflow context and a list of statistically common next
nodes, ask a small LLM to describe what the ideal next node should do. That
description is embedded and used as the semantic search query, rather than
embedding the raw workflow graph directly (which embeds poorly).

If no LLM provider is configured (no ANTHROPIC_API_KEY / GEMINI_API_KEY /
local Ollama endpoint), falls back to a deterministic template so the rest of
the pipeline is still testable end-to-end without any external dependency.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
OLLAMA_URL = os.getenv("OLLAMA_URL")  # e.g. http://localhost:11434
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _build_prompt(last_node_name: str, workflow_name: str | None, common_next: list[str]) -> str:
    context_line = f'Workflow: "{workflow_name}". ' if workflow_name else ""
    hints = ", ".join(common_next) if common_next else "no strong statistical hints available"
    return (
        f"{context_line}The workflow's most recent node is: {last_node_name}. "
        f"Nodes that commonly follow it in similar workflows: {hints}. "
        "In one sentence, describe what the ideal next node in this workflow should do. "
        "Be concrete about the action, not the specific n8n node name."
    )


def _fallback_spec(last_node_name: str, common_next: list[str]) -> str:
    if common_next:
        similar_to = ", ".join(common_next)
        return f"A node that follows '{last_node_name}', similar in purpose to: {similar_to}."
    return f"A node that naturally continues the workflow after '{last_node_name}'."


async def generate_next_node_spec(
    last_node_name: str,
    workflow_name: str | None,
    common_next: list[str],
) -> str:
    prompt = _build_prompt(last_node_name, workflow_name, common_next)

    if ANTHROPIC_API_KEY:
        return await _call_anthropic(prompt)
    if GEMINI_API_KEY:
        return await _call_gemini(prompt)
    if OLLAMA_URL:
        return await _call_ollama(prompt)

    return _fallback_spec(last_node_name, common_next)


async def _call_anthropic(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


async def _call_gemini(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _call_ollama(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
