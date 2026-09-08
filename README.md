# n8n Copilot

[![CI](https://github.com/venya10/n8n/actions/workflows/ci.yml/badge.svg)](https://github.com/venya10/n8n/actions/workflows/ci.yml)

A Chrome extension that suggests the next node while building an n8n workflow. It combines two signals: transition statistics (what commonly follows the current node, mined from 494 real public n8n templates) and semantic search over node descriptions (optionally sharpened by an LLM-generated description of the ideal next node — the HyDE technique).

**Live**: [n8n-copilot-api.onrender.com](https://n8n-copilot-api.onrender.com) — try `GET /health` or `POST /suggest` (example request below). Deployed on Render's free tier without a keep-alive pinger, so the first request after ~15 minutes of inactivity takes 30-50s while the container boots and the embedding model loads; everything after that is fast.

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

- `backend/` — FastAPI service exposing `POST /suggest` and `POST /feedback`. Ships with real data (`backend/app/data/`) mined from 494 public n8n.io templates.
- `extension/` — Manifest V3 Chrome extension. Reads the current workflow via n8n's internal REST API, polls for changes, shows a floating (draggable) suggestion panel, and has a popup for backend URL + an "AI-enhanced suggestions" toggle.
- `data_pipeline/` — Scripts that scraped n8n.io's public template gallery and produced `transitions.json` / `node_metadata.json`. Reproducible, not something that needs re-running to use the project.

## Design decisions

**Real data instead of a hand-built sample set.** The project started with 25 hand-typed nodes and invented transition counts — enough to prove the architecture, not enough to mean anything. I scraped 494 real templates from n8n.io's public gallery instead, which surfaced two real bugs in the scraper along the way (broken pagination that silently re-fetched the same 100 templates every time, and a wrong assumption about how deeply the real API nests workflow data) — the kind of thing that only shows up when you point code at a real external system instead of trusting it works.

**An evaluation harness, not eyeballed output.** `data_pipeline/evaluate.py` holds out 20% of the scraped templates (split by template, not by edge, so nothing leaks), mines transition stats from the other 80%, and for every real `from_type -> to_type` edge in the test set, checks where the ranker actually placed the true answer — Recall@K and MRR, the standard metrics for this kind of ranking problem. This is how every quantitative claim below is backed by a number, not an impression.

**The stats/semantic weight (0.9/0.1) is measured, not guessed.** The project originally shipped with a 0.6/0.4 split that nobody had validated. Sweeping the real held-out data showed pure statistical ranking beats every blend on every metric, and blending in more semantic search actively hurts past a weight of ~0.6. The shipped 0.9/0.1 isn't literally 1.0/0.0 — a semantic weight of exactly zero would make the "node type stats has never seen" fallback path degenerate into an arbitrary tie order instead of a real similarity ranking, and 0.1 scored statistically indistinguishably from 0.0 anyway.

**The optional LLM step (HyDE) is validated as a real but modest win, and is off by default.** Without an LLM, the semantic query is a near-constant template sentence ("a node that follows Webhook..."), which measures topical similarity to a node's description, not "what procedurally comes next" — a different question. Testing a real LLM-generated query (Gemini's free tier) confirmed this: dramatically better in isolation (~12x MRR), but only a few points of improvement once blended into the actual ranking, because statistics already does most of the work. Given that modest gain has to be weighed against a second network round-trip per suggestion and a free tier that hit real, measured limits (20 requests/day on one Gemini model, intermittent timeouts on another), it's a per-user toggle in the extension popup rather than a default.

**Repeated node types are allowed, on purpose.** `/suggest` originally filtered out any node type already present anywhere in the workflow, on the assumption that you don't want to see something you already have. The mined data says otherwise — `HTTP Request -> HTTP Request` is the single most common real transition in the entire dataset. Chaining repeated API calls, multiple `Set` nodes, multiple `Code` nodes, etc. is completely normal in real workflows, and that filter was silently suppressing exactly that. Removing it also fixed a quieter problem: the evaluation harness had never applied that filter either, so production was running a stricter, unvalidated ranker than the one every number above was actually measured against.

**Docker + Render over a serverless platform.** The backend loads `sentence-transformers`/PyTorch into memory and needs to keep it loaded across requests — the opposite of the stateless, short-lived model serverless platforms like Vercel/Netlify are built around, and PyTorch alone would likely exceed their function size limits. A small always-on-ish container fits this workload better. Render's free tier meant an out-of-the-box out-of-memory crash (loading the model pushed past 512MB) — fixed by installing the CPU-only PyTorch build instead of the default CUDA-inclusive one, verified by actually running the built image under a matching memory limit locally rather than assuming the fix worked. Exact deployment config is in `render.yaml` at the repo root, a Render "Blueprint" — meaningful mainly to anyone forking this and wanting their own copy running, since this one is already live.

## Evaluating suggestion quality

Reproducible: `cd data_pipeline && pip install -r requirements.txt -r ../backend/requirements.txt && python evaluate.py` (add `--use-llm` or `--use-llm-context` for the LLM-specific comparisons, both of which make real, sampled API calls).

Full findings, in order of investigation:

1. **Weight sweep** (1,547 held-out edges): pure stats (`semantic_weight=0.0`) beat every blend — MRR 0.347, Recall@5 0.547, Recall@10 0.701 — and accuracy fell as semantic weight rose, cratering past 0.6. Checked whether semantic search at least wins on node types stats has never seen (true cold start); it didn't. Shipped weight is `0.9/0.1` (see "Design decisions" above for why not `1.0/0.0`).
2. **Description quality** was the next hypothesis for why semantic search underperformed — 127 of 192 node types had a placeholder `"TODO: ..."` description at the time. Wrote real descriptions for the ~110 highest-usage types (coverage 65→135/192, `fill_top_descriptions.py`) and re-ran the sweep: Recall@10 moved from 0.553 to 0.547 — essentially nothing. Not the bottleneck.
3. **The real explanation was architectural**: the non-LLM query is a near-constant template, which measures topical similarity rather than "what comes next." Tested with a real LLM-generated query on 487 paired edges — dramatically better in isolation (MRR 0.074 vs 0.006), modestly better blended at the shipped weight (MRR 0.345 vs 0.332, Recall@10 0.682 vs 0.655). Confirmed the correct hypothesis, quantified how much it's actually worth.
4. **Whole-workflow context** for the LLM prompt (every other node in the workflow, not just the last one) showed no measurable effect at n=30 (differences smaller than the ~0.09 standard error at that sample size) — ships anyway since it's free at inference time and more honest about what the LLM knows, but isn't claimed as a proven win.
5. **The already-present-filtering fix** (see "Design decisions") wasn't caught by any of the above, because the evaluation harness never had that bug to begin with — it only surfaced from testing the real deployed app against a real workflow and noticing the suggestions looked worse than the data justified.

## Known limitations

- `reader.js`'s workflow-reading endpoint (`/rest/workflows/:id`) is n8n's internal API, not a stable public contract. Verified working against n8n cloud and a local self-hosted Docker instance; not verified against a production self-hosted deployment.
- 135 of 192 node types have a real, written description; the remaining 57 are long-tail community node packages with a placeholder — shown (point 2 above) not to affect ranking accuracy, so this is a cosmetic gap in `/suggest`'s displayed text, not a known accuracy issue.
- `/feedback` nudges transition counts in memory only; a restart forgets everything. A real deployment would persist this.
- The keep-alive pinger mentioned in the live-demo note isn't currently configured, so a cold Render instance is a real (if minor) first-impression risk.

## Running it locally

For anyone verifying this rather than just reading about it.

**Backend** (Docker):
```bash
docker compose up --build
```
Then `curl http://localhost:8000/health` (expects `{"status": "ok", "model_loaded": true}`) and:
```bash
curl -X POST http://localhost:8000/suggest -H "Content-Type: application/json" -d "{\"context\": {\"nodes\": [{\"id\": \"1\", \"type\": \"n8n-nodes-base.webhook\"}], \"last_node_id\": \"1\"}}"
```
Manual alternative: `cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`. Optional: copy `backend/.env.example` to `.env` and set `GEMINI_API_KEY` (free, no local install — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)), `ANTHROPIC_API_KEY`, or `OLLAMA_URL` to enable the LLM step; without any of them, `use_llm: true` falls back to a deterministic template.

**Tests**:
```bash
cd backend && pip install -r requirements-dev.txt && ruff check . && pytest -q
cd extension && npm ci && npm run lint
```
Both also run on every push via [GitHub Actions](.github/workflows/ci.yml).

**Extension**: `chrome://extensions` → Developer Mode → Load unpacked → select `extension/`. Defaults to the live backend above; the popup shows connection status and has the AI-enhanced-suggestions toggle. Needs a real n8n instance to test against (n8n cloud, or `docker run -p 5678:5678 n8nio/n8n` locally) — the suggestion panel appears as nodes are added, and is draggable by its header.

## Rebuilding the dataset

The commands that actually produced `backend/app/data/`:
```bash
cd data_pipeline
pip install -r requirements.txt
python scrape_templates.py --limit 500
python build_transitions.py
python build_node_embeddings.py
python fill_top_descriptions.py
```
Reproducible against more/newer templates; not required to use the project as-is. Restart the backend afterward — it re-embeds `node_metadata.json` on startup.
