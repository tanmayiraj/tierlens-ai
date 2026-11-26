import os
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Application configuration settings for TierLens AI."""

    APP_NAME: str = "TierLens AI"
    VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tierlens.db")

    # Documented frontend origins from API_SPEC.md Section 7 (Vite on :5173)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Document ingestion and storage settings (Milestone 4)
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB per API_SPEC.md Section 4.2
    SAMPLE_DOCS_DIR: str = os.getenv("SAMPLE_DOCS_DIR", str(BASE_DIR / "data" / "sample_docs"))

    # AI / LLM configuration settings (Milestone 4: TASK-023)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # Risk Engine Configuration (Milestone 6: TASK-017)
    RISK_WEIGHTS: dict = {
        "event_severity": 25.0,
        "criticality": 25.0,
        "single_source_exposure": 25.0,
        "buffer_gap": 15.0,
        "regional_risk": 10.0,
    }
    DURATION_BENCHMARK_DAYS: float = 37.5


settings = Settings()
