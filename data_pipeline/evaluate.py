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
    python evaluate.py                  # sweep semantic_weight 0.0 -> 1.0
    python evaluate.py --weight 0.4      # evaluate one specific split
"""

import argparse
import random
import sys
from pathlib import Path

from build_transitions import extract_edges, load_workflow, mine_transitions

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw_templates"
TEST_FRACTION = 0.2
SEED = 0
RANK_CUTOFF = 20  # how deep to look for the real answer before scoring it a miss

# Import the backend's actual ranking code rather than reimplementing it —
# an eval that tests a reimplementation proves nothing about the real app.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services import retrieval, rerank  # noqa: E402


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


def evaluate(
    test_edges: list[tuple[str, str]], candidate_cache: dict, semantic_weight: float
) -> dict:
    recall_at = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_ranks = []
    evaluable = 0

    for from_type, true_to_type in test_edges:
        # Can't meaningfully evaluate a node type semantic search has never
        # heard of (no metadata entry) — same "silently dropped" behavior
        # the real API has via rerank's NODE_BY_TYPE lookup.
        if true_to_type not in retrieval.NODE_BY_TYPE:
            continue
        evaluable += 1

        stats_candidates, semantic_candidates = candidate_cache[from_type]
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weight",
        type=float,
        default=None,
        help="Evaluate one specific semantic_weight (0.0-1.0) instead of sweeping.",
    )
    args = parser.parse_args()

    template_files = list(RAW_DIR.glob("*.json"))
    if not template_files:
        raise SystemExit(f"No templates found in {RAW_DIR}. Run scrape_templates.py first.")

    train_files, test_files = split_templates(template_files)
    print(f"{len(train_files)} train templates, {len(test_files)} test templates\n")

    train_transitions = mine_transitions(train_files)
    test_edges = build_test_edges(test_files)
    print(f"{len(test_edges)} test edges (real from_type -> to_type pairs)\n")

    if not retrieval.load_model():
        raise SystemExit("Semantic search model failed to load — can't evaluate.")

    print("Embedding candidates once per distinct from_type (reused across the weight sweep)...")
    candidate_cache = candidates_by_from_type(test_edges, train_transitions)

    weights = [args.weight] if args.weight is not None else [i / 10 for i in range(11)]

    header = f"{'semantic_weight':>15} | {'evaluable':>9} | {'MRR':>6} | " + " | ".join(
        f"R@{k}" for k in (1, 3, 5, 10)
    )
    print(header)
    print("-" * len(header))
    for w in weights:
        result = evaluate(test_edges, candidate_cache, w)
        if result["evaluable"] == 0:
            print(f"{w:>15.1f} | no evaluable edges")
            continue
        print(
            f"{w:>15.1f} | {result['evaluable']:>9} | {result['mrr']:>6.3f} | "
            + " | ".join(f"{result[f'recall@{k}']:.3f}" for k in (1, 3, 5, 10))
        )


if __name__ == "__main__":
    main()
