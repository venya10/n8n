# n8n Copilot

[![CI](https://github.com/venya10/n8n/actions/workflows/ci.yml/badge.svg)](https://github.com/venya10/n8n/actions/workflows/ci.yml)

A Chrome extension that suggests the next node while you build an n8n workflow, using a hybrid of:

1. **Transition statistics** — what commonly follows the current node, mined from public n8n templates.
2. **Semantic search** — a vector search over node descriptions, queried either directly or via an LLM-generated ("HyDE") description of the ideal next node.

## Live demo

`https://<your-render-service>.onrender.com` — see [Deploying](#deploying) to get this URL.

The free tier spins down after 15 minutes of inactivity, so the first request after a while takes 30-50s (container boot + loading the embedding model) — worth knowing before demoing it live.

## Architecture

```
extension (Chrome, MV3)          backend (FastAPI)
┌─────────────────────┐          ┌───────────────────────────┐
│ reader.js             │  poll   │ POST /suggest               │
│  reads workflow via   │────────>│  transition stats           │
│  n8n's REST API       │         │  + semantic search           │
│                        │<────────│  (+ optional LLM/HyDE step)  │
│ overlay.js             │ suggest │ POST /feedback               │
│  shows ranked panel   │────────>│  nudges transition weights   │
└─────────────────────┘         └───────────────────────────┘
```

- `backend/` — FastAPI service exposing `POST /suggest` and `POST /feedback`. Ships with real data (`backend/app/data/`) mined from 494 public n8n.io templates, so it runs standalone with zero external services or API keys.
- `extension/` — Manifest V3 Chrome extension. Reads the current workflow via n8n's internal REST API, polls for changes, and shows a floating suggestion panel.
- `data_pipeline/` — Scripts that scrape n8n.io's public template gallery and regenerate `transitions.json` / `node_metadata.json` from it. Already run once to produce the data the backend ships with — rerun it any time to refresh against more/newer templates.

## Running the backend

**Docker (recommended):**

```bash
docker compose up --build
```

**Manually:**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Either way, check `GET http://localhost:8000/health` — it reports `{"status": "ok", "model_loaded": true}` once the embedding model has finished loading.

Try it:

```bash
curl -X POST http://localhost:8000/suggest -H "Content-Type: application/json" -d "{\"context\": {\"nodes\": [{\"id\": \"1\", \"type\": \"n8n-nodes-base.webhook\"}], \"last_node_id\": \"1\"}}"
```

Optional: copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY` (or `OLLAMA_URL` + `OLLAMA_MODEL`) to enable the HyDE step, then pass `"use_llm": true` in the request. Without either configured, a deterministic template fallback is used so the pipeline still runs end-to-end.

## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

```bash
cd extension
npm ci
npm run lint
```

Both run on every push via [GitHub Actions](.github/workflows/ci.yml).

## Loading the extension

1. Go to `chrome://extensions`, enable Developer Mode.
2. "Load unpacked" → select the `extension/` folder.
3. Click the extension icon and confirm the backend URL (defaults to `http://localhost:8000`; the popup shows whether it's reachable).
4. Open a workflow in n8n (self-hosted `localhost:5678` or n8n cloud) — the suggestion panel appears bottom-right as you add nodes.

## Deploying

The backend deploys to [Render](https://render.com)'s free tier as a Docker web service, using the [`render.yaml`](render.yaml) blueprint at the repo root:

1. Push this repo to GitHub (already done if you're reading it there).
2. In the Render dashboard: **New** → **Blueprint** → pick this repo → **Apply**.
3. Render builds `backend/Dockerfile` and deploys it; `envVars` in `render.yaml` are left blank on purpose (`sync: false`) — fill in `ANTHROPIC_API_KEY` etc. in the Render dashboard if you want the LLM step, or leave them unset.
4. Once it's live, `GET https://<service>.onrender.com/health` should return `{"status": "ok", "model_loaded": true}`.

## Rebuilding the dataset

```bash
cd data_pipeline
pip install -r requirements.txt
python scrape_templates.py --limit 500
python build_transitions.py
python build_node_embeddings.py
python fill_top_descriptions.py   # real descriptions for the ~40 highest-usage node types
```

`fill_top_descriptions.py` only covers the highest-usage node types (by mined transition volume) — anything outside that list keeps a `"TODO: write a real description for ..."` placeholder. Semantic search quality for those types is weaker until someone writes a real one; check `backend/app/data/node_metadata.json` for the current TODO count.

Restart the backend afterward — it re-embeds `node_metadata.json` into an in-memory matrix on startup (brute-force cosine similarity; fine up to a few thousand node types).

## Known limitations

- **`reader.js`'s REST endpoint is verified against n8n cloud**, reading real workflow state via `fetch('/rest/workflows/:id')` successfully. It's still n8n's internal API, not a stable public contract, and self-hosted n8n hasn't been checked — if you're on self-hosted, verify the response shape against your version's Network tab before relying on it.
- **~65 of 192 node types have real descriptions** (the 25 originally hand-curated, plus the ~40 highest-usage types from real data); the rest are long-tail community node packages with a placeholder description — see [Rebuilding the dataset](#rebuilding-the-dataset).
- **`/feedback` is in-memory only** — it nudges `stats.py`'s transition counts for the life of the process, then resets on restart. A real deployment would persist this to a small database instead.
- **`use_llm: true` is off by default** in the extension (`background.js` always sends `use_llm: false`) — the HyDE prompt in `backend/app/services/llm.py` works but hasn't been tuned.
