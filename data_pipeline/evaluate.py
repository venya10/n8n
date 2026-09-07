"""Offline evaluation of the suggestion ranking against real held-out data.

The question this answers: if you only show someone a workflow up to some
node, does the ranker actually predict what node they added next in real
life? That's measurable, because the 494 scraped templates are real
workflows someone actually built — each connection in them is a real
"given this node, what came next" example we can test against.

Method: split templates 80/20 by template (not by edge — edges from the
same template must stay on the same side, or stats mined from a template
could "predict" an edge from that same template it was mined from). Mine
transitions.json from the train split only. For every edge in the test
split, ask the same ranking code the backend uses ("given from_type, rank
candidate next nodes") and check whether it found the real to_type, and
how highly it ranked it. Repeat across a sweep of stats/semantic weights
to see which split actually performs best, rather than trusting the
0.6/0.4 default that shipped without any evaluation behind it.

Metrics (standard for ranked recommendation, not invented for this):
- Recall@K: fraction of test edges where the real next node appears
  somewhere in the top K suggestions.
- MRR (Mean Reciprocal Rank): average of 1/rank of the real next node
  (0 if it doesn't appear in the top RANK_CUTOFF at all). Rewards ranking
  the right answer 1st over merely including it somewhere in the top 10.

Usage:
    python evaluate.py                     # sweep semantic_weight 0.0 -> 1.0
    python evaluate.py --weight 0.4         # evaluate one specific split
    python evaluate.py --use-llm            # does the HyDE query beat the plain
                                             # template query, on a small sample?
    python evaluate.py --use-llm --sample 200
    python evaluate.py --use-llm-context    # does a whole-workflow snapshot beat
                                             # a last-node-only HyDE prompt?
"""

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

import httpx

from build_transitions import extract_edges, load_workflow, mine_transitions

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw_templates"
TEST_FRACTION = 0.2
SEED = 0
RANK_CUTOFF = 20  # how deep to look for the real answer before scoring it a miss
DEFAULT_LLM_SAMPLE_SIZE = 60
DEFAULT_CONTEXT_SAMPLE_SIZE = 30  # 2 LLM calls per item here, so kept smaller
LLM_HINT_TOP_K = 5  # matches suggest.py's req.top_k default for the common_next hint
LLM_CALL_DELAY_SECONDS = 4.5  # observed free-tier limit is much stricter than 1/sec

# Import the backend's actual ranking code rather than reimplementing it —
# an eval that tests a reimplementation proves nothing about the real app.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services import llm, retrieval, rerank  # noqa: E402


def split_templates(template_files: list[Path]) -> tuple[list[Path], list[Path]]:
    shuffled = sorted(template_files)  # sort first so shuffle is deterministic across OSes
    random.Random(SEED).shuffle(shuffled)
    cutoff = int(len(shuffled) * (1 - TEST_FRACTION))
    return shuffled[:cutoff], shuffled[cutoff:]


def build_test_edges(test_files: list[Path]) -> list[tuple[str, str]]:
    edges = []
    for path in test_files:
        workflow = load_workflow(path)
        if workflow is None:
            continue
        edges.extend(extract_edges(workflow))
    return edges


def build_test_edges_with_context(
    test_files: list[Path],
) -> list[tuple[str, str, list[str]]]:
    """Like build_test_edges, but also captures every other real node type
    present in that edge's originating workflow — for testing whether
    giving the LLM prompt a snapshot of the whole workflow (not just the
    last node) produces a better HyDE query. to_type itself is excluded
    from that "other nodes" list: it's the answer being predicted, and a
    real /suggest caller couldn't have it in their workflow yet either.
    """
    items = []
    for path in test_files:
        workflow = load_workflow(path)
        if workflow is None:
            continue
        all_types = list(
            dict.fromkeys(n["type"] for n in workflow.get("nodes", []) if n.get("type"))
        )
        for from_type, to_type in extract_edges(workflow):
            other_types = [t for t in all_types if t != to_type]
            items.append((from_type, to_type, other_types))
    return items


async def run_llm_context_comparison(test_files: list[Path], train_transitions: dict, sample_size: int) -> None:
    """Does passing a snapshot of the whole workflow (not just the last
    node) to the LLM produce a better HyDE query than run_llm_comparison's
    already-validated last-node-only prompt? Samples individual edges, not
    distinct from_types like the other comparisons — two edges sharing a
    from_type can come from different workflows with different surrounding
    nodes, which is exactly the variable being tested, so they can't share
    one cached query the way the from_type-only prompt could.
    """
    items = build_test_edges_with_context(test_files)
    rng = random.Random(SEED)
    rng.shuffle(items)
    sampled = items[:sample_size]
    print(
        f"Sampling {len(sampled)} individual edges "
        f"(2 LLM calls each: with and without workflow context)...\n"
    )

    without_context_candidates = []
    with_context_candidates = []
    kept_to_types = []

    for i, (from_type, to_type, other_types) in enumerate(sampled):
        stats_candidates = sorted(
            train_transitions.get(from_type, []), key=lambda e: e["count"], reverse=True
        )[:RANK_CUTOFF]
        meta = retrieval.NODE_BY_TYPE.get(from_type)
        from_name = meta["display_name"] if meta else from_type
        hint_candidates = stats_candidates[:LLM_HINT_TOP_K]
        common_next_names = [
            retrieval.NODE_BY_TYPE[c["to"]]["display_name"]
            for c in hint_candidates
            if c["to"] in retrieval.NODE_BY_TYPE
        ]
        other_names = [
            retrieval.NODE_BY_TYPE[t]["display_name"] if t in retrieval.NODE_BY_TYPE else t
            for t in other_types
        ]

        query_without = await _generate_spec_with_retry(from_name, common_next_names)
        time.sleep(LLM_CALL_DELAY_SECONDS)
        query_with = await _generate_spec_with_retry(from_name, common_next_names, other_names)
        time.sleep(LLM_CALL_DELAY_SECONDS)

        if query_without is None or query_with is None:
            print(f"  ({i + 1}/{len(sampled)}) skipped {from_type} -> {to_type}: a call failed")
            continue

        without_context_candidates.append(
            (
                stats_candidates,
                retrieval.semantic_search(query_without, top_k=RANK_CUTOFF, exclude={from_type}),
            )
        )
        with_context_candidates.append(
            (
                stats_candidates,
                retrieval.semantic_search(query_with, top_k=RANK_CUTOFF, exclude={from_type}),
            )
        )
        kept_to_types.append(to_type)

    print(f"\n{len(kept_to_types)}/{len(sampled)} edges succeeded on both calls\n")

    for weight, weight_label in [(1.0, "pure semantic"), (0.1, "shipped default (0.9/0.1)")]:
        print(f"=== semantic_weight={weight} ({weight_label}) ===")
        _print_table(
            [
                ("without context", evaluate_indexed(kept_to_types, without_context_candidates, weight)),
                ("with context", evaluate_indexed(kept_to_types, with_context_candidates, weight)),
            ]
        )
        print()


def candidates_by_from_type(test_edges: list[tuple[str, str]], train_transitions: dict) -> dict:
    """Precomputes stats/semantic candidates once per distinct from_type.

    Both only depend on from_type, not on the stats/semantic weight — the
    weight only affects how merge_and_rank combines them. Sweeping 11
    weights should cost 11x the (cheap, pure-Python) merge step, not 11x the
    (expensive, model.encode()) semantic search — this cache is what makes
    that true instead of accidentally re-embedding the same query 11 times.
    """
    cache = {}
    for from_type, _ in test_edges:
        if from_type in cache:
            continue
        stats_candidates = sorted(
            train_transitions.get(from_type, []), key=lambda e: e["count"], reverse=True
        )[:RANK_CUTOFF]
        meta = retrieval.NODE_BY_TYPE.get(from_type)
        from_name = meta["display_name"] if meta else from_type
        query = f"a node that follows {from_name} in an n8n workflow"
        semantic_candidates = retrieval.semantic_search(
            query, top_k=RANK_CUTOFF, exclude={from_type}
        )
        cache[from_type] = (stats_candidates, semantic_candidates)
    return cache


async def _generate_spec_with_retry(
    from_name: str, common_next_names: list[str], other_nodes: list[str] | None = None
) -> str | None:
    """Retries on 429 (rate limit) and network-level errors (timeouts,
    connection resets) with backoff. A flat per-call delay isn't a reliable
    enough guarantee to skip retrying — and this must catch httpx.HTTPError
    broadly, not just HTTPStatusError: an uncaught httpx.ReadTimeout here
    once took down an entire multi-minute run, losing every call's progress
    to one transient network hiccup.
    Returns None (caller skips this item) if it still fails after
    retrying — a real error, not just a transient one, should still surface.
    """
    delays = [LLM_CALL_DELAY_SECONDS, 15, 30]
    for attempt, delay in enumerate(delays):
        try:
            return await llm.generate_next_node_spec(
                from_name, None, common_next_names, other_nodes
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == len(delays) - 1:
                print(f"  (LLM call failed for {from_name!r}: {exc} - skipping)")
                return None
            time.sleep(delay)
        except httpx.HTTPError as exc:
            if attempt == len(delays) - 1:
                print(f"  (LLM call failed for {from_name!r}: {exc} - skipping)")
                return None
            time.sleep(delay)
    return None


async def candidates_by_from_type_llm(distinct_from_types: list[str], train_transitions: dict) -> dict:
    """Same idea as candidates_by_from_type, but the semantic query comes
    from llm.generate_next_node_spec (the HyDE step) instead of the plain
    "a node that follows X" template — mirrors exactly what suggest.py does
    when use_llm=True, including capping the common_next hint at
    LLM_HINT_TOP_K (suggest.py's req.top_k default), not RANK_CUTOFF.
    """
    cache = {}
    for from_type in distinct_from_types:
        stats_candidates = sorted(
            train_transitions.get(from_type, []), key=lambda e: e["count"], reverse=True
        )[:RANK_CUTOFF]
        meta = retrieval.NODE_BY_TYPE.get(from_type)
        from_name = meta["display_name"] if meta else from_type

        hint_candidates = stats_candidates[:LLM_HINT_TOP_K]
        common_next_names = [
            retrieval.NODE_BY_TYPE[c["to"]]["display_name"]
            for c in hint_candidates
            if c["to"] in retrieval.NODE_BY_TYPE
        ]

        query = await _generate_spec_with_retry(from_name, common_next_names)
        time.sleep(LLM_CALL_DELAY_SECONDS)
        if query is None:
            continue

        semantic_candidates = retrieval.semantic_search(
            query, top_k=RANK_CUTOFF, exclude={from_type}
        )
        cache[from_type] = (stats_candidates, semantic_candidates)
    return cache


def _score(rows, semantic_weight: float) -> dict:
    """Shared scoring loop. rows: iterable of (true_to_type, stats_candidates,
    semantic_candidates) — the actual data source varies (a from_type-keyed
    cache for the sweeps/plain-vs-HyDE comparison, a parallel per-edge list
    for the workflow-context comparison below), but the scoring math is the
    same either way.
    """
    recall_at = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_ranks = []
    evaluable = 0

    for true_to_type, stats_candidates, semantic_candidates in rows:
        # Can't meaningfully evaluate a node type semantic search has never
        # heard of (no metadata entry) — same "silently dropped" behavior
        # the real API has via rerank's NODE_BY_TYPE lookup.
        if true_to_type not in retrieval.NODE_BY_TYPE:
            continue
        evaluable += 1

        suggestions = rerank.merge_and_rank(
            stats_candidates,
            semantic_candidates,
            top_k=RANK_CUTOFF,
            stats_weight=1 - semantic_weight,
            semantic_weight=semantic_weight,
        )
        ranked_types = [s.node_type for s in suggestions]

        if true_to_type in ranked_types:
            rank = ranked_types.index(true_to_type) + 1
            reciprocal_ranks.append(1 / rank)
            for k in recall_at:
                if rank <= k:
                    recall_at[k] += 1
        else:
            reciprocal_ranks.append(0.0)

    if evaluable == 0:
        return {"evaluable": 0}

    return {
        "evaluable": evaluable,
        "mrr": sum(reciprocal_ranks) / evaluable,
        **{f"recall@{k}": v / evaluable for k, v in recall_at.items()},
    }


def evaluate(
    test_edges: list[tuple[str, str]], candidate_cache: dict, semantic_weight: float
) -> dict:
    # Not in the cache means either it's outside this run's sample, or
    # (llm mode only) the LLM call for it failed and was skipped.
    rows = (
        (true_to_type, *candidate_cache[from_type])
        for from_type, true_to_type in test_edges
        if from_type in candidate_cache
    )
    return _score(rows, semantic_weight)


def evaluate_indexed(
    true_to_types: list[str], candidates: list[tuple[list[dict], list[dict]]], semantic_weight: float
) -> dict:
    """Like evaluate(), but for the workflow-context comparison below, where
    candidates are computed per-edge (not per-from_type — two edges sharing
    a from_type can come from different workflows with different
    surrounding nodes, which is exactly the thing being tested) and so are
    already aligned to true_to_types by position, not by a from_type key.
    """
    rows = (
        (true_to_type, stats_c, semantic_c)
        for true_to_type, (stats_c, semantic_c) in zip(true_to_types, candidates)
    )
    return _score(rows, semantic_weight)


def _print_table(rows: list[tuple[str, dict]]) -> None:
    header = f"{'':>18} | {'evaluable':>9} | {'MRR':>6} | " + " | ".join(
        f"R@{k}" for k in (1, 3, 5, 10)
    )
    print(header)
    print("-" * len(header))
    for label, result in rows:
        if result["evaluable"] == 0:
            print(f"{label:>18} | no evaluable edges")
            continue
        print(
            f"{label:>18} | {result['evaluable']:>9} | {result['mrr']:>6.3f} | "
            + " | ".join(f"{result[f'recall@{k}']:.3f}" for k in (1, 3, 5, 10))
        )


async def run_llm_comparison(
    test_edges: list[tuple[str, str]], train_transitions: dict, sample_size: int
) -> None:
    """Does the LLM/HyDE query beat the plain template query? Compares both
    on the *same* sampled subset — sampled by distinct from_type (not by
    edge) so the number of real LLM calls is bounded and predictable.

    Reports two things:
    - semantic_weight=1.0 (pure semantic, stats zeroed out): isolates
      whether the LLM query makes semantic search itself better, since the
      full-sweep result already showed stats dominates and can mask this.
    - semantic_weight=0.1 (the shipped default): the actual real-world
      impact on /suggest's output, stats included.
    """
    distinct_from_types = list({from_type for from_type, _ in test_edges})
    random.Random(SEED).shuffle(distinct_from_types)
    sampled_types = set(distinct_from_types[:sample_size])
    sampled_edges = [(f, t) for f, t in test_edges if f in sampled_types]
    print(
        f"Sampling {len(sampled_types)} distinct from_types "
        f"({len(sampled_edges)} edges) - bounds real LLM calls to {len(sampled_types)}.\n"
    )

    print("Building plain-template candidates (baseline)...")
    plain_cache = candidates_by_from_type(sampled_edges, train_transitions)

    delay_estimate = len(sampled_types) * LLM_CALL_DELAY_SECONDS
    print(
        f"Building LLM/HyDE candidates ({len(sampled_types)} real API calls, "
        f"~{delay_estimate:.0f}s minimum, more on rate-limit retries)..."
    )
    llm_cache = await candidates_by_from_type_llm(list(sampled_types), train_transitions)
    print(f"  {len(llm_cache)}/{len(sampled_types)} LLM calls succeeded\n")

    # Fairness matters here: only compare on edges whose from_type actually
    # got a real LLM-generated query. Evaluating "plain" on every sampled
    # edge while "LLM" only covers whichever from_types happened to succeed
    # would silently compare two different, non-random subsets — not the
    # same experiment.
    succeeded_types = set(llm_cache.keys())
    paired_edges = [(f, t) for f, t in sampled_edges if f in succeeded_types]
    if len(succeeded_types) < len(sampled_types):
        print(
            f"Restricting comparison to the {len(succeeded_types)} from_types with a successful "
            f"LLM call ({len(paired_edges)} edges) so both sides are evaluated on the same data.\n"
        )

    for weight, weight_label in [(1.0, "pure semantic"), (0.1, "shipped default (0.9/0.1)")]:
        print(f"=== semantic_weight={weight} ({weight_label}) ===")
        _print_table(
            [
                ("plain template", evaluate(paired_edges, plain_cache, weight)),
                ("LLM/HyDE query", evaluate(paired_edges, llm_cache, weight)),
            ]
        )
        print()

    # If the LLM query is meaningfully better in isolation (weight=1.0 above)
    # but that improvement barely moved the shipped-default blend, the most
    # likely explanation is that 0.9/0.1 was tuned for the plain template
    # query and is no longer the right split once semantic search actually
    # has real signal to contribute. Sweeping here costs nothing extra —
    # it's the same cached candidates, just re-run through merge_and_rank
    # at different weights, no further API calls.
    print("=== Full weight sweep on this sample, using the LLM/HyDE query ===")
    _print_table(
        [(f"{w / 10:.1f}", evaluate(paired_edges, llm_cache, w / 10)) for w in range(11)]
    )
    print()
    print("=== Same sweep, plain template query (for comparison) ===")
    _print_table(
        [(f"{w / 10:.1f}", evaluate(paired_edges, plain_cache, w / 10)) for w in range(11)]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weight",
        type=float,
        default=None,
        help="Evaluate one specific semantic_weight (0.0-1.0) instead of sweeping.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Compare the LLM/HyDE query against the plain template query, on a sample.",
    )
    parser.add_argument(
        "--use-llm-context",
        action="store_true",
        help="Compare last-node-only vs whole-workflow-snapshot LLM prompts, on a sample.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help=(
            f"Sample size for --use-llm (default {DEFAULT_LLM_SAMPLE_SIZE} distinct from_types) "
            f"or --use-llm-context (default {DEFAULT_CONTEXT_SAMPLE_SIZE} edges, 2 calls each)."
        ),
    )
    args = parser.parse_args()

    template_files = list(RAW_DIR.glob("*.json"))
    if not template_files:
        raise SystemExit(f"No templates found in {RAW_DIR}. Run scrape_templates.py first.")

    train_files, test_files = split_templates(template_files)
    print(f"{len(train_files)} train templates, {len(test_files)} test templates\n")

    train_transitions = mine_transitions(train_files)

    if not retrieval.load_model():
        raise SystemExit("Semantic search model failed to load — can't evaluate.")

    if args.use_llm_context:
        sample_size = args.sample if args.sample is not None else DEFAULT_CONTEXT_SAMPLE_SIZE
        asyncio.run(run_llm_context_comparison(test_files, train_transitions, sample_size))
        return

    test_edges = build_test_edges(test_files)
    print(f"{len(test_edges)} test edges (real from_type -> to_type pairs)\n")

    if args.use_llm:
        sample_size = args.sample if args.sample is not None else DEFAULT_LLM_SAMPLE_SIZE
        asyncio.run(run_llm_comparison(test_edges, train_transitions, sample_size))
        return

    print("Embedding candidates once per distinct from_type (reused across the weight sweep)...")
    candidate_cache = candidates_by_from_type(test_edges, train_transitions)

    weights = [args.weight] if args.weight is not None else [i / 10 for i in range(11)]
    _print_table(
        [(f"{w:.1f}", evaluate(test_edges, candidate_cache, w)) for w in weights]
    )


if __name__ == "__main__":
    main()
