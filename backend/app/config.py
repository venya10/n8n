"""Central place for reading environment configuration.

Kept deliberately simple (plain `os.getenv`, no settings library) since the
handful of values here don't need validation beyond "is it set".
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Comma-separated list of allowed origins, e.g. "https://app.n8n.cloud,http://localhost:5678".
# Defaults to "*" because the extension can run against n8n cloud, a
# self-hosted instance, or localhost — the origin isn't known ahead of time.
# Set this explicitly if you deploy the backend somewhere with sensitive data.
_raw_cors_origins = os.getenv("CORS_ORIGINS", "*")
if _raw_cors_origins == "*":
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [o.strip() for o in _raw_cors_origins.split(",")]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
