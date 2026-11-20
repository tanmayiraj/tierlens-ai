import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tierlens.db")

# Enforce foreign key constraints on SQLite connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite") or str(dbapi_connection).lower().find("sqlite") != -1:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db(target_engine=None):
    """
    Initializes all 17 database tables and the optional review_queue view.
    Safe to call repeatedly; creates tables if they do not exist.
    """
    import backend.models.db  # noqa: F401 - registers all 17 models on Base.metadata
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

    # Create optional review_queue view as defined in DATABASE_SCHEMA.md Section 3.18
    with eng.connect() as conn:
        conn.execute(text("""
            CREATE VIEW IF NOT EXISTS review_queue AS
            SELECT r.id, s.name AS supplier, b.name AS buyer, m.name AS material,
                   r.confidence, e.snippet, d.filename
            FROM relationships r
            JOIN suppliers s ON s.id = r.supplier_id
            JOIN suppliers b ON b.id = r.buyer_id
            JOIN materials m ON m.id = r.material_id
            LEFT JOIN evidence e ON e.id = r.evidence_id
            LEFT JOIN documents d ON d.id = e.document_id
            WHERE r.status = 'pending'
            ORDER BY r.confidence ASC;
        """))
        conn.commit()


def get_db():
    """Dependency helper yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
