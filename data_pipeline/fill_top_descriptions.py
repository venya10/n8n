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
    # --- second batch: next ~70 by usage after the initial top 40 ---
    "n8n-nodes-base.whatsAppTrigger": (
        "WhatsApp Trigger",
        "trigger",
        "Starts the workflow when a message or event arrives via the "
        "WhatsApp Business Cloud API.",
    ),
    "n8n-nodes-base.nocoDb": (
        "NocoDB",
        "action",
        "Reads, writes, or queries rows in a NocoDB table (an open-source "
        "Airtable alternative).",
    ),
    "n8n-nodes-base.googleDriveTrigger": (
        None,
        "trigger",
        "Starts the workflow when a file changes, is created, or is deleted "
        "in a watched Google Drive folder.",
    ),
    "n8n-nodes-base.hubspot": (
        "HubSpot",
        "action",
        "Creates, updates, or looks up contacts, companies, or deals in "
        "HubSpot CRM.",
    ),
    "n8n-nodes-base.sort": (
        None,
        "transform",
        "Reorders items by one or more fields, ascending or descending.",
    ),
    "n8n-nodes-base.microsoftOutlook": (
        "Microsoft Outlook",
        "action",
        "Sends, reads, or manages emails and calendar events in Microsoft "
        "Outlook.",
    ),
    "n8n-nodes-base.perplexity": (
        "Perplexity",
        "action",
        "Sends a prompt to a Perplexity AI model and returns the generated, "
        "web-grounded answer.",
    ),
    "n8n-nodes-base.github": (
        "GitHub",
        "action",
        "Creates or manages issues, pull requests, files, or repositories on "
        "GitHub.",
    ),
    "n8n-nodes-base.compareDatasets": (
        "Compare Datasets",
        "transform",
        "Compares two sets of items and reports which are new, changed, "
        "removed, or unchanged between them.",
    ),
    "n8n-nodes-base.summarize": (
        None,
        "transform",
        "Aggregates items into summary values (sum, average, count, etc.) "
        "grouped by a field.",
    ),
    "n8n-nodes-base.redis": (
        "Redis",
        "action",
        "Reads, writes, or deletes a key in a Redis in-memory data store.",
    ),
    "n8n-nodes-base.reddit": (
        "Reddit",
        "action",
        "Reads posts/comments from, or posts/comments to, a subreddit via "
        "the Reddit API.",
    ),
    "n8n-nodes-base.executeCommand": (
        "Execute Command",
        "action",
        "Runs a shell command on the machine the n8n instance is hosted on "
        "and returns its output.",
    ),
    "n8n-nodes-base.readBinaryFile": (
        "Read Binary File",
        "action",
        "Reads a file from local disk into the workflow as binary data — "
        "the older predecessor to Read/Write Files from Disk.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStorePinecone": (
        "Pinecone Vector Store",
        "action",
        "Stores or retrieves document embeddings in a Pinecone vector "
        "database, for retrieval-augmented generation.",
    ),
    "n8n-nodes-base.mySql": (
        "MySQL",
        "action",
        "Runs a query against, or inserts/updates rows in, a MySQL "
        "database.",
    ),
    "n8n-nodes-base.airtop": (
        "Airtop",
        "action",
        "Automates actions in a real browser session (clicking, scraping, "
        "extracting) via the Airtop API.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStoreQdrant": (
        "Qdrant Vector Store",
        "action",
        "Stores or retrieves document embeddings in a Qdrant vector "
        "database, for retrieval-augmented generation.",
    ),
    "n8n-nodes-base.xml": (
        "XML",
        "transform",
        "Converts XML text to JSON, or JSON to XML.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStoreSupabase": (
        "Supabase Vector Store",
        "action",
        "Stores or retrieves document embeddings in a Supabase (pgvector) "
        "vector store, for retrieval-augmented generation.",
    ),
    "n8n-nodes-base.salesforce": (
        "Salesforce",
        "action",
        "Creates, updates, or looks up records (leads, contacts, "
        "opportunities) in Salesforce.",
    ),
    "n8n-nodes-base.ssh": (
        "SSH",
        "action",
        "Runs a command on a remote machine over SSH and returns its "
        "output.",
    ),
    "n8n-nodes-base.odoo": (
        "Odoo",
        "action",
        "Creates, updates, or looks up records in an Odoo ERP instance.",
    ),
    "n8n-nodes-base.clickUp": (
        "ClickUp",
        "action",
        "Creates, updates, or looks up tasks in ClickUp.",
    ),
    "n8n-nodes-base.cron": (
        "Cron",
        "trigger",
        "Starts the workflow on a fixed schedule defined by a cron-style "
        "expression — the older predecessor to Schedule Trigger.",
    ),
    "n8n-nodes-base.gitlab": (
        "GitLab",
        "action",
        "Creates or manages issues, merge requests, or files in a GitLab "
        "project.",
    ),
    "n8n-nodes-base.itemLists": (
        "Item Lists",
        "transform",
        "Splits, aggregates, sorts, or removes duplicates from a list of "
        "items — an older node whose functions are now split across Split "
        "Out, Sort, Aggregate, and Remove Duplicates.",
    ),
    "n8n-nodes-base.discord": (
        "Discord",
        "action",
        "Sends a message or embed to a Discord channel via a bot or "
        "webhook.",
    ),
    "n8n-nodes-base.slackTrigger": (
        None,
        "trigger",
        "Starts the workflow when a message or event occurs in a connected "
        "Slack workspace.",
    ),
    "n8n-nodes-base.asana": (
        "Asana",
        "action",
        "Creates, updates, or looks up tasks and projects in Asana.",
    ),
    "n8n-nodes-base.snowflake": (
        "Snowflake",
        "action",
        "Runs a query against a Snowflake data warehouse.",
    ),
    "n8n-nodes-base.wordpress": (
        "WordPress",
        "action",
        "Creates, updates, or looks up posts, pages, or users on a "
        "WordPress site.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStoreInMemory": (
        "Simple Vector Store",
        "action",
        "Stores document embeddings in memory for the duration of the "
        "workflow run, for lightweight retrieval-augmented generation "
        "without an external vector database.",
    ),
    "n8n-nodes-base.evaluation": (
        "Evaluation",
        "flow",
        "Scores a workflow's output against an expected result, for "
        "automated testing of AI/LLM workflows.",
    ),
    "n8n-nodes-base.microsoftExcel": (
        "Microsoft Excel 365",
        "action",
        "Reads or writes rows in an Excel workbook stored in OneDrive/"
        "SharePoint.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStorePGVector": (
        "Postgres PGVector Store",
        "action",
        "Stores or retrieves document embeddings in a Postgres database "
        "using the pgvector extension.",
    ),
    "@n8n/n8n-nodes-langchain.chainSummarization": (
        "Summarization Chain",
        "action",
        "Uses an LLM to summarize a long document or set of input text.",
    ),
    "@n8n/n8n-nodes-langchain.memoryManager": (
        "Chat Memory Manager",
        "action",
        "Reads, writes, or clears an AI Agent's conversation memory buffer.",
    ),
    "n8n-nodes-base.twilio": (
        "Twilio",
        "action",
        "Sends an SMS or makes a call via Twilio.",
    ),
    "n8n-nodes-base.jotFormTrigger": (
        "Jotform Trigger",
        "trigger",
        "Starts the workflow when someone submits a connected Jotform form.",
    ),
    "n8n-nodes-base.sendInBlue": (
        "Brevo",
        "action",
        "Sends a transactional email or manages contacts via Brevo "
        "(formerly Sendinblue).",
    ),
    "n8n-nodes-base.rssFeedReadTrigger": (
        "RSS Feed Trigger",
        "trigger",
        "Starts the workflow when a new item appears in a watched RSS/Atom "
        "feed.",
    ),
    "n8n-nodes-base.writeBinaryFile": (
        "Write Binary File",
        "action",
        "Writes incoming binary data to a file on the local disk the n8n "
        "instance runs on — the older predecessor to Read/Write Files from "
        "Disk.",
    ),
    "n8n-nodes-base.highLevel": (
        "HighLevel",
        "action",
        "Creates, updates, or looks up contacts and records in a HighLevel "
        "(GoHighLevel) CRM account.",
    ),
    "n8n-nodes-base.calTrigger": (
        "Cal.com Trigger",
        "trigger",
        "Starts the workflow when a booking is created, rescheduled, or "
        "cancelled in Cal.com.",
    ),
    "@n8n/n8n-nodes-langchain.code": (
        "LangChain Code",
        "action",
        "Runs custom JavaScript/Python with direct access to LangChain "
        "objects (models, chains, memory) for advanced AI logic.",
    ),
    "@n8n/n8n-nodes-langchain.vectorStoreMongoDBAtlas": (
        "MongoDB Atlas Vector Store",
        "action",
        "Stores or retrieves document embeddings in a MongoDB Atlas vector "
        "search index.",
    ),
    "n8n-nodes-base.aiTransform": (
        "AI Transform",
        "transform",
        "Uses an LLM to transform input data into a described output "
        "shape, generating the transformation logic automatically.",
    ),
    "n8n-nodes-base.ftp": (
        "FTP",
        "action",
        "Uploads, downloads, or lists files on a remote server over "
        "FTP/SFTP.",
    ),
    "@n8n/n8n-nodes-langchain.chat": (
        "Chat",
        "action",
        "Sends or displays a message within an n8n chat interface session.",
    ),
    "@n8n/n8n-nodes-langchain.chainRetrievalQa": (
        "Question and Answer Chain",
        "action",
        "Answers a question by retrieving relevant documents from a vector "
        "store and passing them to an LLM as context.",
    ),
    "n8n-nodes-base.hunter": (
        "Hunter",
        "action",
        "Finds or verifies an email address for a person or domain via "
        "Hunter.io.",
    ),
    "n8n-nodes-base.emailReadImap": (
        "Email Trigger (IMAP)",
        "trigger",
        "Starts the workflow when a new email arrives in a mailbox "
        "monitored over IMAP.",
    ),
    "n8n-nodes-base.webflow": (
        "Webflow",
        "action",
        "Creates, updates, or looks up items in a Webflow CMS collection.",
    ),
    "n8n-nodes-base.awsS3": (
        "AWS S3",
        "action",
        "Uploads, downloads, or lists objects in an Amazon S3 bucket.",
    ),
    "n8n-nodes-base.apiTemplateIo": (
        "APITemplate.io",
        "action",
        "Generates an image or PDF from a template via the APITemplate.io "
        "API.",
    ),
    "n8n-nodes-base.typeformTrigger": (
        "Typeform Trigger",
        "trigger",
        "Starts the workflow when someone submits a connected Typeform.",
    ),
    "n8n-nodes-base.readPDF": (
        "Read PDF",
        "transform",
        "Extracts text content from a PDF file.",
    ),
    "n8n-nodes-base.mailchimp": (
        "Mailchimp",
        "action",
        "Adds or updates a subscriber, or manages campaigns, in Mailchimp.",
    ),
    "n8n-nodes-base.trello": (
        "Trello",
        "action",
        "Creates, updates, or looks up cards and boards in Trello.",
    ),
    "@n8n/n8n-nodes-langchain.guardrails": (
        "Guardrails",
        "flow",
        "Validates an LLM's output against defined rules (e.g. format, "
        "banned content) before it continues downstream.",
    ),
    "n8n-nodes-base.googleCalendarTrigger": (
        "Google Calendar Trigger",
        "trigger",
        "Starts the workflow when an event is created, updated, or starts "
        "soon on a watched Google Calendar.",
    ),
    "n8n-nodes-base.mistralAi": (
        "Mistral AI",
        "action",
        "Sends a prompt to a Mistral AI model and returns the generated "
        "result.",
    ),
    "n8n-nodes-base.wooCommerce": (
        "WooCommerce",
        "action",
        "Creates, updates, or looks up products and orders in a WooCommerce "
        "store.",
    ),
    "n8n-nodes-base.executionData": (
        "Execution Data",
        "flow",
        "Attaches custom metadata to the current workflow execution, "
        "visible in n8n's execution list/log.",
    ),
    "n8n-nodes-base.hackerNews": (
        "Hacker News",
        "action",
        "Reads posts, comments, or user data from Hacker News.",
    ),
    "n8n-nodes-base.debugHelper": (
        "DebugHelper",
        "action",
        "Generates test/dummy data or deliberately throws an error, for "
        "testing workflow logic during development.",
    ),
    "n8n-nodes-base.microsoftTeams": (
        "Microsoft Teams",
        "action",
        "Sends a message to a Microsoft Teams channel or chat.",
    ),
    "n8n-nodes-base.sms77": (
        "seven",
        "action",
        "Sends an SMS message via the seven (sms77) API.",
    ),
    "n8n-nodes-base.googleAnalytics": (
        "Google Analytics",
        "action",
        "Reads report data from a Google Analytics property.",
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
