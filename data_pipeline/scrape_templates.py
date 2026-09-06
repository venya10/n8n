"""Downloads public n8n workflow templates via n8n.io's template API.

This is the raw corpus the rest of the pipeline mines for node-transition
statistics and node vocabulary. Writes one JSON file per template into
data/raw_templates/.

Usage:
    python scrape_templates.py --limit 500
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from tqdm import tqdm

API_BASE = "https://api.n8n.io/api/templates"
OUT_DIR = Path(__file__).resolve().parent / "data" / "raw_templates"


async def fetch_template_ids(client: httpx.AsyncClient, limit: int) -> list[int]:
    ids = []
    page = 1  # 1-indexed — the API silently ignores "skip"/"offset" and just
    # re-returns page 1 for those, so this used to fetch the same 100
    # templates forever regardless of `limit`.
    per_page = 100
    while len(ids) < limit:
        resp = await client.get(
            f"{API_BASE}/search",
            params={"rows": per_page, "page": page},
        )
        resp.raise_for_status()
        data = resp.json()
        workflows = data.get("workflows", [])
        if not workflows:
            break
        ids.extend(w["id"] for w in workflows)
        page += 1
    return ids[:limit]


async def fetch_and_save_template(client: httpx.AsyncClient, template_id: int) -> None:
    out_path = OUT_DIR / f"{template_id}.json"
    if out_path.exists():
        return
    resp = await client.get(f"{API_BASE}/workflows/{template_id}")
    if resp.status_code != 200:
        return
    out_path.write_text(json.dumps(resp.json()), encoding="utf-8")


async def main(limit: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=20) as client:
        ids = await fetch_template_ids(client, limit)
        for template_id in tqdm(ids, desc="Downloading templates"):
            await fetch_and_save_template(client, template_id)
            await asyncio.sleep(0.1)  # be polite to n8n's API


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(main(args.limit))
