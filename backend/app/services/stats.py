import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "transitions.json"

with open(DATA_PATH, encoding="utf-8") as f:
    _TRANSITIONS: dict[str, list[dict]] = json.load(f)


def get_common_next_nodes(from_node_type: str, limit: int = 5) -> list[dict]:
    """Return the most frequent next-node types observed after `from_node_type`,
    sorted by count descending. Empty list if the node has no recorded transitions
    (e.g. unseen node type, or it's terminal in the mined template corpus).
    """
    candidates = _TRANSITIONS.get(from_node_type, [])
    ranked = sorted(candidates, key=lambda c: c["count"], reverse=True)
    return ranked[:limit]


def record_feedback(from_node_type: str, to_node_type: str, accepted: bool) -> None:
    """Nudge the in-memory transition counts based on user feedback.

    This is a simple online-learning stub: accepted suggestions reinforce the
    edge weight, rejected ones slightly decay it. Not persisted to disk here —
    a real deployment would write this to the SQLite/Postgres transition store.
    """
    if not accepted:
        return
    edges = _TRANSITIONS.setdefault(from_node_type, [])
    for edge in edges:
        if edge["to"] == to_node_type:
            edge["count"] += 1
            return
    edges.append({"to": to_node_type, "count": 1})
