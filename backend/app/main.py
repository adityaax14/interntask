"""
SwasthiQ EOD Billing & Analytics Agent — FastAPI Application.

Entry point: uvicorn app.main:app --reload --port 8000
"""

import os
import time
import threading
import urllib.request
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def start_keep_alive():
    """Pings the Render external URL every 10 minutes to prevent the free tier from sleeping."""
    hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        return
        
    url = f"https://{hostname}/health"
    print(f"Starting keep-alive daemon for {url}")
    
    def ping_loop():
        while True:
            time.sleep(600)  # 10 minutes
            try:
                urllib.request.urlopen(url, timeout=10)
                print(f"Keep-alive ping sent to {url}")
            except Exception as e:
                print(f"Keep-alive ping failed: {e}")
                
    thread = threading.Thread(target=ping_loop, daemon=True)
    thread.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_keep_alive()
    yield

app = FastAPI(
    title="SwasthiQ EOD Billing & Analytics Agent",
    description="REST API for clinic billing reconciliation, analytics, and AI narrative summaries.",
    version="1.0.0",
    lifespan=lifespan,
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
