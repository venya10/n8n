# n8n Copilot

Chrome extension that suggests the next node while you build an n8n workflow, using a hybrid of:
1. **Transition statistics** — what commonly follows the current node, mined from public n8n templates.
2. **Semantic search** — a vector DB of node descriptions, queried either directly or via an LLM-generated ("HyDE") description of the ideal next node.

## Structure

- `backend/` — FastAPI service exposing `POST /suggest`. Ships with hand-curated sample data (`backend/app/data/`) so it runs standalone with zero external services or API keys.
- `extension/` — Manifest V3 Chrome extension. Reads the current workflow via n8n's internal REST API, polls for changes, and shows a floating suggestion panel.
- `data_pipeline/` — Scripts to scrape real n8n templates and regenerate `transitions.json` / `node_metadata.json` at scale, replacing the sample data.

## Running the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

Try it:
```bash
curl -X POST http://localhost:8000/suggest -H "Content-Type: application/json" -d "{\"context\": {\"nodes\": [{\"id\": \"1\", \"type\": \"n8n-nodes-base.webhook\"}], \"last_node_id\": \"1\"}}"
```

Optional: set `ANTHROPIC_API_KEY` (or `OLLAMA_URL` + `OLLAMA_MODEL`) in a `.env` file in `backend/` and pass `"use_llm": true` in the request to enable the HyDE step. Without either configured, a deterministic template fallback is used so the pipeline still runs end-to-end.

## Loading the extension

1. Go to `chrome://extensions`, enable Developer Mode.
2. "Load unpacked" → select the `extension/` folder.
3. Click the extension icon and confirm the backend URL (defaults to `http://localhost:8000`).
4. Open a workflow in n8n (self-hosted `localhost:5678` or n8n cloud) — the suggestion panel appears bottom-right as you add nodes.

**Known spike risk**: the content script reads workflow state via `fetch('/rest/workflows/:id')`. This is n8n's internal API, not a stable public contract — verify it against your n8n version's Network tab before relying on it, and adjust `extension/src/content/reader.js` if the path/response shape has changed.

## Rebuilding the real dataset

```bash
cd data_pipeline
pip install -r requirements.txt
python scrape_templates.py --limit 500
python build_transitions.py
python build_node_embeddings.py   # then hand-fill any "TODO" descriptions it flags
```

Restart the backend afterward — it re-embeds `node_metadata.json` into an in-memory matrix on startup (brute-force cosine similarity; fine up to a few thousand node types).

## Suggested next steps

1. Verify `reader.js`'s REST endpoint against a real n8n instance — this gates everything else.
2. Run the data pipeline for real to replace the 25-node sample set.
3. Turn on `use_llm: true` and tune the HyDE prompt in `backend/app/services/llm.py`.
4. Log `/feedback` calls to a real store (currently in-memory) to start closing the loop on suggestion quality.
