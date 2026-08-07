"""
SwasthiQ EOD Billing & Analytics Agent — FastAPI Application.

Entry point: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="SwasthiQ EOD Billing & Analytics Agent",
    description="REST API for clinic billing reconciliation, analytics, and AI narrative summaries.",
    version="1.0.0",
)

# ── CORS (allow React frontend) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routes ─────────────────────────────────────────────────────
from app.routes import router  # noqa: E402

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "SwasthiQ EOD Billing & Analytics Agent",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
