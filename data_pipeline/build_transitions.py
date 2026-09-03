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
    nodes_by_name = {n["name"]: n["type"] for n in workflow.get("nodes", [])}
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


def main() -> None:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    template_files = list(RAW_DIR.glob("*.json"))
    if not template_files:
        raise SystemExit(f"No templates found in {RAW_DIR}. Run scrape_templates.py first.")

    for path in template_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        workflow = data.get("workflow", data)  # API wraps it under "workflow" sometimes
        for from_type, to_type in extract_edges(workflow):
            counts[from_type][to_type] += 1

    transitions = {
        from_type: sorted(
            [{"to": to_type, "count": c} for to_type, c in to_counts.items()],
            key=lambda e: e["count"],
            reverse=True,
        )
        for from_type, to_counts in counts.items()
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(transitions, indent=2), encoding="utf-8")
    print(f"Wrote {len(transitions)} source nodes' transitions to {OUT_PATH}")


if __name__ == "__main__":
    main()
