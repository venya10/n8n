"""Collects the unique node types seen across the scraped templates and
writes backend/app/data/node_metadata.json.

Each downloaded template file is api.n8n.io's response shape:
{"workflow": {..template metadata.., "nodes": [<node-type summary, no
connections>, ...], "workflow": {..the actual n8n workflow..}}}. The outer
"nodes" list is a de-duplicated summary used by the template gallery UI —
it already carries each node type's real `displayName`, which is more
reliable than guessing one from the type string, so that's what this script
reads (see build_transitions.py for why the *inner* "workflow" key holds the
real node instances + connections instead).

n8n's template API doesn't include human-written node descriptions, so
`description` stays a generic placeholder for node types not already present
in the existing node_metadata.json (which was hand-curated for the most
common nodes). Review the output and fill in real descriptions for anything
new — description quality directly drives semantic search quality, so this
step is worth doing by hand rather than trusting the placeholder text.

Usage:
    python build_node_embeddings.py
"""

import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw_templates"
OUT_PATH = (
    Path(__file__).resolve().parent.parent / "backend" / "app" / "data" / "node_metadata.json"
)


def guess_category(node_type: str) -> str:
    lowered = node_type.lower()
    if "trigger" in lowered or "webhook" in lowered:
        return "trigger"
    if any(k in lowered for k in ("if", "switch", "merge", "filter", "wait", "noop")):
        return "flow"
    if any(k in lowered for k in ("set", "code", "aggregate", "datetime")):
        return "transform"
    return "action"


def main() -> None:
    existing: dict[str, dict] = {}
    if OUT_PATH.exists():
        for n in json.loads(OUT_PATH.read_text(encoding="utf-8")):
            existing[n["type"]] = n

    seen: dict[str, str] = {}
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        outer = data.get("workflow", data)
        for node in outer.get("nodes", []):
            node_type = node.get("name")  # yes, "name" holds the type here — see docstring
            if node_type and node_type not in seen:
                seen[node_type] = node.get("displayName") or node_type.split(".")[-1].title()

    merged = dict(existing)
    for node_type, display in seen.items():
        if node_type not in merged:
            merged[node_type] = {
                "type": node_type,
                "display_name": display,
                "category": guess_category(node_type),
                "description": f"TODO: write a real description for {display}.",
            }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(list(merged.values()), indent=2), encoding="utf-8"
    )
    todo_count = sum(1 for n in merged.values() if n["description"].startswith("TODO"))
    print(f"Wrote {len(merged)} node types to {OUT_PATH} ({todo_count} need descriptions).")


if __name__ == "__main__":
    main()
