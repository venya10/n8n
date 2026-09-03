from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.suggest import router as suggest_router

app = FastAPI(title="n8n Copilot API")

# The extension calls this API from an n8n page's origin (varies: cloud
# instance, self-hosted, localhost) so we allow any origin. Restrict this if
# you deploy the backend somewhere with sensitive data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suggest_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
