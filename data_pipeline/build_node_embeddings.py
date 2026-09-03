"""Collects the unique node types seen across the scraped templates and
writes backend/app/data/node_metadata.json.

n8n's template API doesn't include human-written node descriptions, so this
script pulls the display name from the template node data and leaves
`description` as a generic placeholder for node types not already present in
the existing node_metadata.json (which was hand-curated for the most common
nodes). Review the output and fill in real descriptions for anything new —
description quality directly drives semantic search quality, so this step is
worth doing by hand rather than trusting the placeholder text.

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
        workflow = data.get("workflow", data)
        for node in workflow.get("nodes", []):
            node_type = node.get("type")
            if node_type and node_type not in seen:
                # crude display-name guess from the type string, e.g.
                # "n8n-nodes-base.googleSheets" -> "Google Sheets"
                short = node_type.split(".")[-1]
                display = "".join(
                    " " + c if c.isupper() else c for c in short
                ).strip().title()
                seen[node_type] = display

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
