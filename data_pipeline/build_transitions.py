"""Mines (from_node_type -> to_node_type) transition frequencies from the
downloaded template workflows and writes backend/app/data/transitions.json
in the same shape the backend's stats service expects.

Usage:
    python build_transitions.py
"""

import json
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw_templates"
OUT_PATH = (
    Path(__file__).resolve().parent.parent / "backend" / "app" / "data" / "transitions.json"
)


def extract_edges(workflow: dict) -> list[tuple[str, str]]:
    # Real community-submitted templates aren't all well-formed — some node
    # entries are missing "name" or "type" (seen in practice, not
    # hypothetical). Skip those rather than letting one bad template crash
    # the whole mining run.
    nodes_by_name = {
        n["name"]: n["type"] for n in workflow.get("nodes", []) if n.get("name") and n.get("type")
    }
    edges = []
    connections = workflow.get("connections", {})
    for from_name, outputs in connections.items():
        from_type = nodes_by_name.get(from_name)
        if not from_type:
            continue
        for output_group in outputs.get("main", []):
            for conn in output_group or []:
                to_type = nodes_by_name.get(conn.get("node"))
                if to_type:
                    edges.append((from_type, to_type))
    return edges


def load_workflow(path: Path) -> dict | None:
    """Reads one downloaded template file and unwraps it down to the real
    n8n workflow dict (nodes + connections) — see the module docstring note
    above `main()`'s loop for why that's two levels deep, not one. Returns
    None for anything unreadable rather than raising, since these are
    externally-scraped files.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    outer = data.get("workflow", data)
    return outer.get("workflow", outer)


def mine_transitions(template_paths: list[Path]) -> dict[str, list[dict]]:
    """Builds the transitions.json shape from a given set of template files.
    Takes an explicit file list (rather than always globbing RAW_DIR) so
    data_pipeline/evaluate.py can mine stats from a train-only split without
    leaking test-set templates into it.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in template_paths:
        workflow = load_workflow(path)
        if workflow is None:
            continue
        for from_type, to_type in extract_edges(workflow):
            counts[from_type][to_type] += 1

    return {
        from_type: sorted(
            [{"to": to_type, "count": c} for to_type, c in to_counts.items()],
            key=lambda e: e["count"],
            reverse=True,
        )
        for from_type, to_counts in counts.items()
    }


def main() -> None:
    # api.n8n.io wraps the actual n8n workflow (nodes + connections) two
    # levels deep: {"workflow": {..template metadata.., "workflow": {...}}}.
    # The outer "nodes" list is just a de-duplicated node-type summary for
    # the template gallery UI (no connections) — easy to mistake for the
    # real thing, which is why load_workflow() unwraps two levels, not one.
    template_files = list(RAW_DIR.glob("*.json"))
    if not template_files:
        raise SystemExit(f"No templates found in {RAW_DIR}. Run scrape_templates.py first.")

    transitions = mine_transitions(template_files)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(transitions, indent=2), encoding="utf-8")
    print(f"Wrote {len(transitions)} source nodes' transitions to {OUT_PATH}")


if __name__ == "__main__":
    main()
