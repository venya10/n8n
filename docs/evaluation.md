# Evaluation: full methodology and experiment history

This is the detailed record behind the README's evaluation summary — full tables, the investigation order, and the dead ends. Reproduce any of it with `data_pipeline/evaluate.py`.

## Methodology

- **Data**: 494 real workflow templates scraped from n8n.io's public template gallery.
- **Split**: 80/20, by *template* (not by edge) — every edge from a given template stays entirely on one side of the split, so stats mined from a template can never "predict" an edge from that same template.
- **Task**: for every real `from_type -> to_type` edge in the test split, ask the ranker (the actual backend code, not a reimplementation) to rank candidate next nodes given only `from_type`, and check where the real `to_type` landed.
- **Metrics**: Recall@K (did the real answer appear in the top K?) and MRR — mean reciprocal rank, which rewards ranking the right answer 1st over merely including it somewhere in the top 10. Both are standard for ranked recommendation, not invented for this project.
- **1,547 evaluable edges** out of 1,599 in the test split (the remainder reference a node type with no metadata entry at all, so they're excluded rather than silently scored as failures).

## 1. Stats vs. semantic weight sweep

Investigated first, because the shipped weight (originally `0.6/0.4`) had never been validated against anything — just a plausible-sounding guess.

| `semantic_weight` | MRR | R@1 | R@3 | R@5 | R@10 |
|---|---|---|---|---|---|
| 0.0 | 0.347 | 0.191 | 0.424 | 0.547 | 0.701 |
| **0.1 (shipped)** | 0.345 | 0.191 | 0.424 | 0.539 | 0.692 |
| 0.2 | 0.339 | 0.189 | 0.423 | 0.530 | 0.683 |
| 0.3 | 0.330 | 0.189 | 0.411 | 0.511 | 0.637 |
| 0.4 | 0.316 | 0.189 | 0.403 | 0.480 | 0.547 |
| 0.5 | 0.297 | 0.189 | 0.378 | 0.434 | 0.491 |
| 0.6 | 0.224 | 0.131 | 0.282 | 0.328 | 0.381 |
| 0.7 | 0.054 | 0.012 | 0.039 | 0.056 | 0.167 |
| 0.8 | 0.016 | 0.003 | 0.012 | 0.017 | 0.059 |
| 0.9 | 0.008 | 0.001 | 0.002 | 0.003 | 0.023 |
| 1.0 | 0.007 | 0.001 | 0.002 | 0.002 | 0.013 |

Pure statistics wins on every metric, and accuracy falls as semantic weight rises — cratering badly past 0.6. The shipped weight is `0.9/0.1`, not literally `1.0/0.0`:
- A semantic weight of exactly zero degenerates the "node type stats has never seen" fallback path (nothing else to rank by) into an arbitrary tie order instead of a real similarity ranking.
- `0.1` vs `0.0` differ by less than one standard error at this sample size (≈0.017 on Recall@10, vs. an observed gap of 0.009) — statistically indistinguishable, so there's no real accuracy cost to keeping semantic search functional for that edge case.

Also checked the more charitable hypothesis — that semantic search would at least win on node types stats has *never seen* (true cold start, no frequency signal available): stratified out the 30 such edges and tested weights 0.0/0.4/0.6/1.0 separately. Semantic search didn't help there either — Recall@1/5/10 were all exactly 0 regardless of weight.

## 2. Description quality (ruled out)

At the time of experiment 1, 127 of 192 node types carried a placeholder `"TODO: write a real description for ..."` instead of real prose — the obvious next hypothesis for why semantic search underperformed.

Wrote real descriptions for the ~110 highest-usage node types by mined transition volume (`fill_top_descriptions.py`), taking coverage from 65/192 to 135/192. Re-ran the full sweep: Recall@10 at `semantic_weight=0.4` moved from 0.553 to 0.547 — a decrease, and the cold-start slice stayed at exactly 0 recall regardless of weight, before and after. Description quality was not the bottleneck.

## 3. LLM/HyDE query quality

The real explanation was architectural, not data quality: without an LLM, the semantic query is `"a node that follows {previous_node_name} in an n8n workflow"` — a near-constant template, compared against descriptions of what each candidate node *does*. That measures topical similarity, not "what procedurally tends to come next" — a different question.

Tested with a real LLM-generated query (`--use-llm`, via Gemini's free tier) on 48 `from_type`s / 487 edges, paired so both sides evaluate on identical data:

| | MRR | R@1 | R@5 | R@10 |
|---|---|---|---|---|
| weight=1.0 (isolated) — plain template | 0.006 | 0.002 | 0.002 | 0.006 |
| weight=1.0 (isolated) — LLM query | 0.074 | 0.037 | 0.117 | 0.146 |
| weight=0.1 (shipped) — plain template | 0.332 | 0.195 | 0.501 | 0.655 |
| weight=0.1 (shipped) — LLM query | 0.345 | 0.214 | 0.503 | 0.682 |

Isolated (semantic search alone, stats zeroed out), the LLM query is dramatically better — confirms the architectural hypothesis. Blended at the shipped weight, the improvement is real but modest (a few points of Recall@10), because statistics already does most of the ranking work regardless of query quality. Re-sweeping the full weight range using the LLM query instead of the template still peaks around `semantic_weight≈0.1` — turning the LLM on doesn't change what weight is optimal.

**Free-tier reliability, measured rather than assumed**: `gemini-3.6-flash`'s free tier caps at 20 requests/day total (read directly from the 429 response body's quota-exceeded message). Switched the default to `gemini-flash-lite-latest`, which held up much better but still threw intermittent `503`s and timeouts under this evaluation's sustained call rate — a production system would need a paid tier or a self-hosted model (Ollama) to use this reliably.

## 4. Whole-workflow context for the LLM prompt

Originally the HyDE prompt only knew the single most recent node — a 10-node workflow and a 1-node workflow got an identical prompt as long as their last node matched. Extended it to include every other node already in the workflow (deduplicated, excluding the true answer being predicted to avoid leaking it).

Tested (`--use-llm-context`) on 30 real edges, one real LLM call each way per edge (paired):

| | MRR | R@1 | R@3 | R@5 | R@10 |
|---|---|---|---|---|---|
| weight=1.0 — without context | 0.097 | 0.067 | 0.067 | 0.100 | 0.167 |
| weight=1.0 — with context | 0.113 | 0.067 | 0.133 | 0.167 | 0.167 |
| weight=0.1 — without context | 0.283 | 0.133 | 0.300 | 0.433 | 0.733 |
| weight=0.1 — with context | 0.276 | 0.133 | 0.300 | 0.400 | 0.733 |

At n=30, the standard error on proportions like these is roughly ±0.09 — every difference in this table is within noise. No conclusion either way; the feature ships anyway because it costs nothing extra at inference time and is more honest about what the LLM actually knows, but it isn't a demonstrated win. A meaningfully larger sample (likely requiring a paid API tier to run without hours of rate-limit waiting) would be needed to detect an effect this small, if one exists.

## 5. The already-present-filtering fix (found outside the harness)

`/suggest` originally filtered out any node type already present anywhere in the current workflow. This wasn't caught by any experiment above, because `evaluate.py` never applied that filter to begin with (it only ever excludes the current node's own type from the semantic step, to stop a node's embedding trivially matching itself). It surfaced from testing the real deployed app against a real screenshot and noticing the suggestions looked weaker than the mined data justified.

Per the mined data, `HTTP Request -> HTTP Request` is the single most common real transition in the entire dataset — chaining repeated node types is normal in real workflows, and the filter was silently suppressing exactly that. Removed it; `suggest.py` now matches what `evaluate.py` had been measuring all along, rather than silently running a stricter, unvalidated ranker in production.

Verified against `Manual Trigger -> Set -> HTTP Request`: previously 3 of 5 suggestion slots were weak semantic-only fallbacks (scores ≈0.06) because `Set` and `HTTP Request` were excluded from the stats candidate pool; afterward, all 5 slots are filled by real, strong stats candidates, with `HTTP Request` correctly back as the top pick.
