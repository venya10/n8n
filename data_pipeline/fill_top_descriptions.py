"""One-off script: fills in real descriptions for the highest-usage node
types that build_node_embeddings.py left as TODO placeholders, ranked by
how often they actually appear in the mined transitions.json. Covers the
~40 types that matter most for suggestion quality; the long tail of
rarely-used community node packages keeps its placeholder description.

Usage:
    python fill_top_descriptions.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "data"
META_PATH = DATA_DIR / "node_metadata.json"

# type -> (display_name override or None, category, description)
DESCRIPTIONS: dict[str, tuple[str | None, str, str]] = {
    "@n8n/n8n-nodes-langchain.agent": (
        "AI Agent",
        "action",
        "Runs an autonomous LLM agent that can reason over the input and call "
        "other connected tools/nodes to complete a task, rather than just "
        "generating a single text response.",
    ),
    "@n8n/n8n-nodes-langchain.openAi": (
        "OpenAI",
        "action",
        "Sends a prompt to an OpenAI model (chat, image, or audio) and returns "
        "the generated result.",
    ),
    "n8n-nodes-base.googleDrive": (
        None,
        "action",
        "Uploads, downloads, moves, or searches files and folders in Google Drive.",
    ),
    "n8n-nodes-base.splitOut": (
        None,
        "transform",
        "Splits a single item's array field into multiple separate items, one "
        "per array element, so downstream nodes process them individually.",
    ),
    "@n8n/n8n-nodes-langchain.chainLlm": (
        "Basic LLM Chain",
        "action",
        "Sends a prompt (with an optional template) to a connected LLM and "
        "returns its response — a single-step chain, no tool use or memory.",
    ),
    "n8n-nodes-base.extractFromFile": (
        None,
        "transform",
        "Extracts text or structured data out of a binary file (PDF, CSV, "
        "spreadsheet, etc.) into workflow JSON.",
    ),
    "n8n-nodes-base.formTrigger": (
        None,
        "trigger",
        "Starts the workflow when someone submits n8n's built-in web form — "
        "no external service needed to collect input.",
    ),
    "@n8n/n8n-nodes-langchain.chatTrigger": (
        "Chat Trigger",
        "trigger",
        "Starts the workflow from n8n's built-in chat widget, turning the "
        "workflow into a conversational chatbot.",
    ),
    "n8n-nodes-base.executeWorkflow": (
        "Execute Sub-workflow",
        "action",
        "Calls another n8n workflow as a reusable sub-routine and passes data "
        "into it.",
    ),
    "n8n-nodes-base.telegramTrigger": (
        None,
        "trigger",
        "Starts the workflow when a message or event arrives in a connected "
        "Telegram bot.",
    ),
    "n8n-nodes-base.googleDocs": (
        None,
        "action",
        "Creates, reads, or updates the content of a Google Docs document.",
    ),
    "n8n-nodes-base.dataTable": (
        "Data table",
        "action",
        "Reads or writes rows in an n8n Data Table — a small built-in "
        "database for persisting data between workflow runs.",
    ),
    "n8n-nodes-base.emailSend": (
        "Send Email",
        "action",
        "Sends an email via SMTP, with optional attachments.",
    ),
    "n8n-nodes-base.facebookGraphApi": (
        "Facebook Graph API",
        "action",
        "Makes a call to Meta's Graph API for Facebook/Instagram — posting, "
        "reading, or managing pages and content.",
    ),
    "n8n-nodes-base.whatsApp": (
        "WhatsApp Business Cloud",
        "action",
        "Sends or receives WhatsApp messages via Meta's WhatsApp Business "
        "Cloud API.",
    ),
    "n8n-nodes-base.function": (
        "Function",
        "transform",
        "Runs custom JavaScript against the input items — the older, "
        "single-item-at-a-time predecessor to the Code node.",
    ),
    "n8n-nodes-base.convertToFile": (
        None,
        "transform",
        "Converts workflow JSON data into a binary file (CSV, JSON, ICS, "
        "etc.) for output or attachment.",
    ),
    "n8n-nodes-base.rssFeedRead": (
        "RSS Read",
        "action",
        "Fetches and parses items from an RSS/Atom feed URL.",
    ),
    "n8n-nodes-base.limit": (
        None,
        "flow",
        "Caps the number of items passed downstream, keeping only the first "
        "N (or last N) items.",
    ),
    "n8n-nodes-base.googleCalendar": (
        None,
        "action",
        "Creates, updates, or looks up events on a Google Calendar.",
    ),
    "n8n-nodes-base.html": (
        "HTML",
        "transform",
        "Extracts data from HTML content using CSS selectors, or builds an "
        "HTML string from workflow data.",
    ),
    "n8n-nodes-base.form": (
        "n8n Form",
        "action",
        "Renders an additional page/step in a multi-step n8n form flow, "
        "collecting more input from the same user session.",
    ),
    "@n8n/n8n-nodes-langchain.textClassifier": (
        "Text Classifier",
        "action",
        "Uses an LLM to sort input text into one of several predefined "
        "categories.",
    ),
    "@n8n/n8n-nodes-langchain.googleGemini": (
        "Google Gemini",
        "action",
        "Sends a prompt to a Google Gemini model and returns the generated "
        "result.",
    ),
    "@n8n/n8n-nodes-langchain.informationExtractor": (
        "Information Extractor",
        "action",
        "Uses an LLM to pull structured fields (per a defined schema) out of "
        "unstructured input text.",
    ),
    "n8n-nodes-base.executeWorkflowTrigger": (
        None,
        "trigger",
        "Marks a workflow as callable by an Execute Sub-workflow node from "
        "another workflow, and defines the inputs it expects.",
    ),
    "n8n-nodes-base.youTube": (
        "YouTube",
        "action",
        "Uploads videos or reads channel/video data via the YouTube API.",
    ),
    "n8n-nodes-base.linkedIn": (
        "LinkedIn",
        "action",
        "Posts content or reads profile/company data via the LinkedIn API.",
    ),
    "n8n-nodes-base.supabase": (
        None,
        "action",
        "Reads, writes, or queries rows in a Supabase (Postgres-backed) "
        "table.",
    ),
    "n8n-nodes-base.gmailTrigger": (
        None,
        "trigger",
        "Starts the workflow when a new email matching a filter arrives in a "
        "connected Gmail account.",
    ),
    "n8n-nodes-base.n8n": (
        "n8n",
        "action",
        "Calls n8n's own management API — listing, triggering, or updating "
        "other workflows/executions on the same instance.",
    ),
    "n8n-nodes-base.googleSheetsTrigger": (
        None,
        "trigger",
        "Starts the workflow when a row is added or a cell changes in a "
        "watched Google Sheet.",
    ),
    "n8n-nodes-base.microsoftOneDrive": (
        "Microsoft OneDrive",
        "action",
        "Uploads, downloads, or searches files and folders in OneDrive.",
    ),
    "n8n-nodes-base.editImage": (
        "Edit Image",
        "transform",
        "Resizes, crops, rotates, or overlays text/images on an incoming "
        "binary image.",
    ),
    "n8n-nodes-base.removeDuplicates": (
        None,
        "transform",
        "Filters out items that duplicate ones seen earlier in the same "
        "run or a previous run, based on chosen fields.",
    ),
    "n8n-nodes-base.crypto": (
        "Crypto",
        "transform",
        "Hashes, signs, or encrypts/decrypts data (e.g. HMAC, SHA256, RSA) "
        "within the workflow.",
    ),
    "n8n-nodes-base.readWriteFile": (
        "Read/Write Files from Disk",
        "action",
        "Reads a file from, or writes workflow data to, the local disk the "
        "n8n instance runs on.",
    ),
    "n8n-nodes-base.markdown": (
        "Markdown",
        "transform",
        "Converts Markdown text to HTML, or HTML back to Markdown.",
    ),
    "n8n-nodes-base.stopAndError": (
        "Stop and Error",
        "flow",
        "Deliberately fails the workflow execution with a custom error "
        "message — used to halt on a condition that shouldn't continue.",
    ),
    "n8n-nodes-base.twitter": (
        "X (Formerly Twitter)",
        "action",
        "Posts, reads, or searches posts on X (Twitter) via its API.",
    ),
}


def main() -> None:
    nodes = json.loads(META_PATH.read_text(encoding="utf-8"))
    updated = 0
    for n in nodes:
        entry = DESCRIPTIONS.get(n["type"])
        if entry is None:
            continue
        display_override, category, description = entry
        if display_override:
            n["display_name"] = display_override
        n["category"] = category
        n["description"] = description
        updated += 1

    META_PATH.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    print(f"Updated {updated}/{len(DESCRIPTIONS)} node descriptions in {META_PATH}")


if __name__ == "__main__":
    main()
