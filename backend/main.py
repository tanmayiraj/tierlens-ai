import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
@app.get(f"{settings.API_PREFIX}/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Service health check endpoint as specified in API_SPEC.md Section 4.1.
    Performs a lightweight read-only query (SELECT 1) to verify database connectivity.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    llm_configured = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))
    llm_status = "configured" if llm_configured else "not_configured"

    # Graph service is initialized in Phase 2; report current status
    graph_info = {
        "nodes": 0,
        "edges": 0,
        "last_built": None,
    }

    overall_status = "ok" if db_status == "connected" else "degraded"

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "database": db_status,
        "graph": graph_info,
        "llm": llm_status,
    }
