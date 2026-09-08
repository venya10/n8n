# n8n Copilot

[![CI](https://github.com/venya10/n8n/actions/workflows/ci.yml/badge.svg)](https://github.com/venya10/n8n/actions/workflows/ci.yml)

A Chrome extension that suggests the next node while you build an n8n workflow, using a hybrid of:

1. **Transition statistics** — what commonly follows the current node, mined from public n8n templates.
2. **Semantic search** — a vector search over node descriptions, queried either directly or via an LLM-generated ("HyDE") description of the ideal next node.

## Live demo

**[https://n8n-copilot-api.onrender.com](https://n8n-copilot-api.onrender.com)** — try `GET /health` or `POST /suggest` (see [Running the backend](#running-the-backend) for a full example request).

Render's free tier spins down after 15 minutes of inactivity — **the keep-alive pinger described in [Deploying](#deploying) is not currently set up**, so if this link hasn't been hit recently, expect the first request to take 30-50s (container boot + loading the embedding model) before it responds normally. Hitting `/health` once first is an easy way to "warm it up" before trying `/suggest` or the extension.

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

Optional: copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (free tier, no local install — get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)), or `OLLAMA_URL` + `OLLAMA_MODEL` (fully local) to enable the HyDE step, then pass `"use_llm": true` in the request. Without any of them configured, a deterministic template fallback is used so the pipeline still runs end-to-end.

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
3. Click the extension icon and confirm the backend URL — defaults to the live deployment (`https://n8n-copilot-api.onrender.com`), since most people installing this extension aren't also running the backend locally; point it at `http://localhost:8000` instead if you're developing against a local backend from [Running the backend](#running-the-backend). The popup shows whether the configured URL is actually reachable. It also has an **AI-enhanced suggestions** toggle for `use_llm` (off by default — see [Evaluating suggestion quality](#evaluating-suggestion-quality) for why).
4. Open a workflow in n8n (self-hosted `localhost:5678` or n8n cloud) — the suggestion panel appears bottom-right as you add nodes. It's draggable — grab the header to move it out of the way of n8n's own node search panel.

## Deploying

The backend deploys to [Render](https://render.com)'s free tier as a Docker web service, using the [`render.yaml`](render.yaml) blueprint at the repo root:

1. Push this repo to GitHub (already done if you're reading it there).
2. In the Render dashboard: **New** → **Blueprint** → pick this repo → **Apply**.
3. Render builds `backend/Dockerfile` and deploys it; `envVars` in `render.yaml` are left blank on purpose (`sync: false`) — fill in `ANTHROPIC_API_KEY` etc. in the Render dashboard if you want the LLM step, or leave them unset.
4. Once it's live, `GET https://<service>.onrender.com/health` should return `{"status": "ok", "model_loaded": true}`.

**Avoiding the cold-start wait**: Render's free tier spins the service down after 15 minutes idle, so the first request after that takes 30-50s (container boot + loading the embedding model). Fix it for free with an external uptime pinger instead of upgrading to a paid tier:

1. Sign up at [cron-job.org](https://cron-job.org) (or UptimeRobot, or any similar free service).
2. Create a new cron job hitting `GET https://<your-service>.onrender.com/health`.
3. Set the interval to every 10 minutes (must be under Render's 15-minute idle timeout).
4. Save it — as long as it keeps running, the service never goes idle long enough to spin down, so every request stays fast.

## Rebuilding the dataset

```bash
cd data_pipeline
pip install -r requirements.txt
python scrape_templates.py --limit 500
python build_transitions.py
python build_node_embeddings.py
python fill_top_descriptions.py   # real descriptions for the ~110 highest-usage node types
```

`fill_top_descriptions.py` only covers the highest-usage node types (by mined transition volume) — anything outside that list keeps a `"TODO: write a real description for ..."` placeholder; check `backend/app/data/node_metadata.json` for the current TODO count. Note per [Evaluating suggestion quality](#evaluating-suggestion-quality): filling these in improves the description text `/suggest` displays, but measurably did *not* improve ranking accuracy — don't expect writing more of them to move the eval numbers.

Restart the backend afterward — it re-embeds `node_metadata.json` into an in-memory matrix on startup (brute-force cosine similarity; fine up to a few thousand node types).

## Evaluating suggestion quality

`data_pipeline/evaluate.py` answers "is this actually working?" against real data, not vibes: it splits the 494 scraped templates 80/20 (by template, not by edge, so nothing in the test set leaks into training), mines `transitions.json` from the train split only, and for every real `from_type -> to_type` edge in the test split, asks the backend's actual ranking code to predict `to_type` and checks where it landed. Standard recommender metrics — Recall@K (did the real answer appear in the top K?) and MRR (how high did it rank, on average, rewarding 1st place over merely "somewhere in the top 10").

```bash
cd data_pipeline
pip install -r requirements.txt -r ../backend/requirements.txt  # evaluate.py imports the real backend ranking code
python evaluate.py                # sweeps semantic_weight from 0.0 to 1.0
python evaluate.py --weight 0.1   # evaluate one specific split
python evaluate.py --use-llm       # does the real LLM/HyDE query beat the plain template query?
python evaluate.py --use-llm-context  # does a whole-workflow snapshot beat a last-node-only prompt?
```

**What it found**, against 1,547 evaluable held-out edges: pure transition-frequency ranking (`semantic_weight=0.0`) beat every blend on every metric (MRR 0.347, Recall@5 0.547, Recall@10 0.701), and got *worse*, not better, as semantic search's weight increased — cratering badly past 0.6. The `0.6/0.4` split this shipped with originally was never validated against anything; it was a plausible-sounding guess. It's now `0.9/0.1` (see `backend/app/services/rerank.py`) — not literally `1.0/0.0`, because a semantic weight of exactly zero would degenerate the "unknown node type" fallback path (nothing else to rank by) to an arbitrary tie-order instead of a real similarity ranking, and 0.1 scored statistically indistinguishably from 0.0 anyway (the gap is smaller than one standard error at this sample size).

Checked the more charitable hypothesis too — that semantic search would at least win on node types stats has *never seen* (true cold start, where there's no frequency signal to fall back on): stratifying the 30 such edges out separately, semantic search still didn't help there either.

**The obvious next guess was description quality** — at the time of that first measurement, 127 of 192 node types still carried a placeholder `"TODO: ..."` description instead of real prose. So that got fixed: coverage went from 65/192 to 135/192 real descriptions (see `fill_top_descriptions.py`). Re-running the full sweep afterward moved almost nothing — Recall@10 at `semantic_weight=0.4` went from 0.553 to 0.547, and the cold-start slice stayed at exactly 0 regardless of weight, before and after. So description quality wasn't the bottleneck after all.

The more likely explanation is architectural, not data quality: without the LLM/HyDE step (`use_llm=True`, off by default), the semantic query is just `"a node that follows {previous_node_name} in an n8n workflow"` — a near-constant template sentence, compared against descriptions of what each candidate node *does*. That measures topical similarity, not "what procedurally tends to come next", which is a different question. So that got tested directly.

**Testing `use_llm=True` itself**: `python evaluate.py --use-llm [--sample N]` compares the plain template query against a real LLM-generated one (via Gemini's free tier) on a sample of `from_type`s, paired so both sides evaluate on identical edges. Real API calls, so it's sampled (default 60 distinct `from_type`s) rather than run over the full test set. Result, on a 48-`from_type`/487-edge sample:

- **In isolation** (`semantic_weight=1.0`, stats zeroed out), the LLM query is dramatically better than the plain template — MRR 0.074 vs 0.006 (~12x), Recall@10 0.146 vs 0.006 (~24x). The architectural hypothesis was right: a real "what should come next" description genuinely makes semantic search smarter, confirming the earlier guess wasn't just an excuse.
- **But re-sweeping the full weight range using the LLM query**, the blended optimum barely moves — still peaking around `semantic_weight≈0.1`, same as with the plain template, because stats-based ranking simply outperforms semantic search (of either kind) everywhere in the useful weight range. At the shipped `0.9/0.1` split specifically, `use_llm=True` gives a small, real improvement (MRR 0.345 vs 0.332, Recall@10 0.682 vs 0.655) — real, but modest.
- On top of that modest gain, real free-tier LLM calls introduce genuine unreliability worth knowing about first-hand rather than assuming: `gemini-3.6-flash`'s free tier turned out to cap at **20 requests/day** (confirmed by reading the actual 429 response body, not guessing), and the lighter `gemini-flash-lite-latest` returned intermittent `503`s under this evaluation's sustained call rate. A production system would need a paid tier or a self-hosted model (Ollama) to use this reliably, not the free tier.

**Conclusion**: `use_llm=True` is a real, validated improvement, but a modest one, and the honest tradeoff is added latency + a third-party dependency (rate-limited or paid) per suggestion for a few points of Recall@10. Leaving it off by default is a defensible call, not just an oversight — turn it on if you have a properly provisioned LLM backend and want the small quality bump.

**Does the LLM prompt need the whole workflow, or just the last node?** Originally the HyDE prompt only knew the single most recent node — a 10-node workflow and a 1-node workflow got the identical prompt as long as their last node matched. `generate_next_node_spec` now also takes a snapshot of every other node already in the workflow (`suggest.py` builds this from `ctx.nodes`, deduplicated, excluding the last node itself and — critically for a fair test — excluding the true answer being predicted). `python evaluate.py --use-llm-context [--sample N]` compares last-node-only vs whole-workflow-snapshot prompts, one real LLM call each way per sampled edge (paired, so it's apples-to-apples). Result, on 30 real edges:

- **In isolation** (`semantic_weight=1.0`): a small positive nudge (MRR 0.113 vs 0.097, Recall@5 0.167 vs 0.100) — but at n=30 the standard error on proportions like these is roughly ±0.09, so this is within noise, not a demonstrated win.
- **At the shipped default** (`semantic_weight=0.1`): essentially a wash, if anything marginally worse (MRR 0.276 vs 0.283) — again noise-level, not a real regression.

**Conclusion**: no measurable effect either way at a sample size a free-tier API can actually afford (30 edges × 2 calls each already took several minutes and hit real rate limits along the way). The feature ships anyway — it costs nothing extra at inference time (same one LLM call, just a longer prompt) and is more honest about what the LLM actually knows — but "gives the LLM more context" turned out not to be the thing that was limiting `use_llm`'s quality here. A meaningfully larger sample (probably requiring a paid tier to run without hours of rate-limit waiting) would be needed to detect an effect this small, if one exists at all.

**One more thing worth knowing: repeated node types are allowed, on purpose.** `/suggest` used to filter out every node type already present anywhere in the workflow, on the reasoning that you probably don't want to see something you already have. Real data says otherwise: `HTTP Request -> HTTP Request` is the single most common real transition in the entire mined dataset — chaining multiple calls, multiple `Set` nodes, multiple `Code` nodes, etc. is completely normal in real n8n workflows, and the old filter silently suppressed exactly that. It also meant production was quietly running a *stricter* ranker than the one `evaluate.py` had ever measured — the eval harness only ever excluded the current node's own type from the semantic step (to stop it trivially matching itself), never a running list of everything already used. `suggest.py` now matches that: stats candidates aren't filtered by workflow contents at all, and semantic search only excludes the current node's own type. Verified against a real screenshot (`Manual Trigger -> Set -> HTTP Request`): previously 3 of 5 suggestion slots were weak semantic-only fallbacks because `Set` and `HTTP Request` were excluded from the stats pool; now all 5 are filled by real, strong stats candidates, including "HTTP Request" as the top pick.

## Known limitations

- **`reader.js`'s REST endpoint is verified against n8n cloud**, reading real workflow state via `fetch('/rest/workflows/:id')` successfully. It's still n8n's internal API, not a stable public contract, and self-hosted n8n hasn't been checked — if you're on self-hosted, verify the response shape against your version's Network tab before relying on it.
- **135 of 192 node types have real descriptions** (the original 25 plus ~110 filled in by usage volume — see `fill_top_descriptions.py`); the remaining 57 are long-tail community node packages with a placeholder description. Per the evaluation section above, filling these in did *not* meaningfully change ranking quality — so this is now a "nice to have" for `/suggest`'s displayed description text, not a lever expected to move suggestion accuracy.
- **`/feedback` is in-memory only** — it nudges `stats.py`'s transition counts for the life of the process, then resets on restart. A real deployment would persist this to a small database instead.
- **"AI-enhanced suggestions" is off by default**, toggleable per-user in the extension popup (persisted to `chrome.storage.sync`, read by `background.js` per request) — validated as a real but modest improvement (see above), traded off against the latency and reliability of a per-suggestion LLM call on a free-tier API.
