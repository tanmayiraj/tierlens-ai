import os
from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models.db import Supplier, Plant, ProductionLine
from backend.api.suppliers import router as suppliers_router
from backend.api.relationships import router as relationships_router
from backend.api.graph import router as graph_router
from backend.api.documents import router as documents_router
from backend.api.risk import router as risk_router
from backend.api.simulation import router as simulation_router

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


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom validation error handler adhering to API_SPEC.md Section 1.3:
    {"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {...}}}
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Field-level validation failed.",
                "details": {"errors": exc.errors()},
            }
        },
    )


# Register API routers
app.include_router(suppliers_router, prefix=settings.API_PREFIX)
app.include_router(suppliers_router)
app.include_router(relationships_router, prefix=settings.API_PREFIX)
app.include_router(relationships_router)
app.include_router(graph_router, prefix=settings.API_PREFIX)
app.include_router(graph_router)
app.include_router(documents_router, prefix=settings.API_PREFIX)
app.include_router(documents_router)
app.include_router(risk_router, prefix=settings.API_PREFIX)
app.include_router(risk_router)
app.include_router(simulation_router, prefix=settings.API_PREFIX)
app.include_router(simulation_router)


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

    # Report current graph state (explicit rebuilding is handled via POST /graph/rebuild)
    from backend.graph.service import graph_service

    if graph_service.is_built:
        production_line_count = db.query(ProductionLine).count()

        graph_info = {
            "nodes": graph_service.node_count + production_line_count,
            "edges": graph_service.edge_count,
            "last_built": graph_service.built_at.isoformat() if graph_service.built_at else None,
        }
    else:
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
