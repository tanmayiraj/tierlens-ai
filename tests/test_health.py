"""
Verification tests for the FastAPI health-check endpoint.
Tests route registration, CORS middleware, OpenAPI schema, response contract,
and database connectivity checking on an isolated test database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app, health_check
from backend.config import settings
from backend.database import Base


@pytest.fixture
def isolated_db_session(tmp_path):
    """
    Creates an isolated temporary SQLite database session.
    Never modifies or resets the development database.
    """
    test_db_file = tmp_path / "test_health_isolated.db"
    test_engine = create_engine(
        f"sqlite:///{test_db_file.as_posix()}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


def test_health_endpoint_routes_registered():
    """Verifies /health and /api/v1/health are registered with GET method."""
    route_map = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}
    assert "/health" in route_map, "Exact path /health is not registered"
    assert "GET" in route_map["/health"]
    assert "/api/v1/health" in route_map, "Prefix path /api/v1/health is not registered"
    assert "GET" in route_map["/api/v1/health"]


def test_cors_middleware_configured():
    """Verifies CORS middleware is configured with documented origins."""
    cors_middlewares = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert len(cors_middlewares) > 0, "CORSMiddleware is not registered on app"
    cors_options = cors_middlewares[0].kwargs
    assert "http://localhost:5173" in cors_options.get("allow_origins", [])


def test_openapi_schema_contract():
    """Verifies FastAPI generates valid OpenAPI documentation for /health."""
    schema = app.openapi()
    assert schema["info"]["title"] == "TierLens AI"
    assert schema["info"]["version"] == "0.1.0"
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]


def test_health_check_response_structure_and_connectivity(isolated_db_session):
    """
    Verifies health_check function returns the exact response contract
    specified in API_SPEC.md Section 4.1 when database is connected.
    """
    data = health_check(db=isolated_db_session)

    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["database"] == "connected"
    assert "graph" in data
    assert isinstance(data["graph"], dict)
    assert data["graph"]["nodes"] == 0
    assert data["graph"]["edges"] == 0
    assert data["graph"]["last_built"] is None
    assert data["llm"] in ("configured", "not_configured")


def test_health_check_database_disconnected():
    """
    Verifies health_check accurately reports 'disconnected' and 'degraded'
    when the database query fails, and does not falsely report 'connected'.
    """
    class BrokenDBSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("Simulated database failure")

    data = health_check(db=BrokenDBSession())

    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
    assert data["version"] == settings.VERSION


def test_health_check_llm_status_reporting(isolated_db_session, monkeypatch):
    """Verifies LLM configuration detection based on environment variables."""
    # When no key is set
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    data = health_check(db=isolated_db_session)
    assert data["llm"] == "not_configured"

    # When key is set
    monkeypatch.setenv("GEMINI_API_KEY", "test_key_123")
    data_with_llm = health_check(db=isolated_db_session)
    assert data_with_llm["llm"] == "configured"
