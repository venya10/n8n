import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS, LOG_LEVEL
from app.routes.suggest import router as suggest_router
from app.services import retrieval

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not retrieval.load_model():
        logger.warning("Starting with semantic search disabled (model failed to load)")
    yield


app = FastAPI(title="n8n Copilot API", lifespan=lifespan)

# The extension calls this API from an n8n page's origin (varies: cloud
# instance, self-hosted, localhost) so CORS_ORIGINS defaults to "*". Set it
# to a specific list via the CORS_ORIGINS env var if you deploy the backend
# somewhere with sensitive data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suggest_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model_loaded": retrieval.is_ready()}


@app.get("/")
async def root() -> dict:
    return {
        "name": "n8n Copilot API",
        "docs": "/docs",
        "health": "/health",
        "repo": "https://github.com/venya10/n8n",
    }
