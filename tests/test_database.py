"""
Automated verification tests for TierLens AI database schema and seeding.
Uses an isolated temporary SQLite database to avoid touching the development database.
"""

import pytest
from sqlalchemy import create_engine, inspect, event, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.database import init_db
from backend.models.db import Supplier, Material, Relationship, Evidence
from backend.seed import seed_database


@pytest.fixture
def isolated_engine(tmp_path):
    """
    Creates an isolated temporary SQLite database for testing.
    Guarantees no modifications to the development tierlens.db.
    """
    db_file = tmp_path / "test_isolated.db"
    test_db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(target_engine=engine)
    yield engine
    engine.dispose()


def test_schema_creates_all_17_tables_and_view(isolated_engine):
    """Verifies all 17 tables and the review_queue view are created in SQLite."""
    inspector = inspect(isolated_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "documents",
        "suppliers",
        "supplier_aliases",
        "materials",
        "supplier_materials",
        "evidence",
        "relationships",
        "relationship_evidence",
        "plants",
        "products",
        "production_lines",
        "line_requirements",
        "events",
        "alerts",
        "alert_affected_nodes",
        "scenarios",
        "scenario_results",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify review_queue view
    view_names = set(inspector.get_view_names())
    assert "review_queue" in view_names, "review_queue view was not created"


def test_schema_creates_all_11_indexes(isolated_engine):
    """Verifies all 11 documented indexes from DATABASE_SCHEMA.md Section 5 are present."""
    with isolated_engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex%';"))
        index_names = {row[0] for row in result.fetchall()}

    expected_indexes = {
        "idx_rel_supplier",
        "idx_rel_buyer",
        "idx_rel_material",
        "idx_rel_status",
        "idx_evidence_doc",
        "idx_alias_alias",
        "idx_events_supplier",
        "idx_alerts_event",
        "idx_alerts_status",
        "idx_affected_alert",
        "idx_supmat_material",
    }
    assert expected_indexes.issubset(index_names), f"Missing indexes: {expected_indexes - index_names}"


def test_foreign_key_enforcement_active(isolated_engine):
    """Verifies PRAGMA foreign_keys=ON blocks orphan child inserts."""
    with Session(isolated_engine) as session:
        # Attempt to insert evidence pointing to non-existent document_id=9999
        orphan_evidence = Evidence(
            document_id=9999,
            snippet="Orphan snippet without valid document",
        )
        session.add(orphan_evidence)
        with pytest.raises(IntegrityError):
            session.commit()


def test_self_supply_check_constraint(isolated_engine):
    """Verifies CHECK (supplier_id <> buyer_id) blocks self-supply relationships."""
    seed_database(target_engine=isolated_engine)

    with Session(isolated_engine) as session:
        sup = session.query(Supplier).first()
        mat = session.query(Material).first()

        self_supply = Relationship(
            supplier_id=sup.id,
            buyer_id=sup.id,  # Invalid: self-supply
            material_id=mat.id,
            status="pending",
        )
        session.add(self_supply)
        with pytest.raises(IntegrityError):
            session.commit()


def test_unique_constraint_on_supplier_name(isolated_engine):
    """Verifies UNIQUE (name) constraint on suppliers table."""
    with Session(isolated_engine) as session:
        sup1 = Supplier(name="UniqueCo", entity_type="supplier")
        sup2 = Supplier(name="UniqueCo", entity_type="supplier")
        session.add(sup1)
        session.commit()

        session.add(sup2)
        with pytest.raises(IntegrityError):
            session.commit()


def test_seeded_relationships_tier_is_null(isolated_engine):
    """Verifies relationships.tier remains NULL on seed (deferred to graph service)."""
    seed_database(target_engine=isolated_engine)

    with Session(isolated_engine) as session:
        relationships = session.query(Relationship).all()
        assert len(relationships) > 0, "No relationships seeded"
        for rel in relationships:
            assert rel.tier is None, f"Relationship {rel.id} has non-null tier: {rel.tier}"


def test_evidence_first_linkage(isolated_engine):
    """Verifies seeded relationships link to valid evidence and documents with synthetic label."""
    seed_database(target_engine=isolated_engine)

    with Session(isolated_engine) as session:
        approved_rels = session.query(Relationship).filter(Relationship.status == "approved").all()
        assert len(approved_rels) > 0

        for rel in approved_rels:
            assert rel.evidence_id is not None, f"Approved relationship {rel.id} missing evidence_id"
            evidence = session.query(Evidence).filter(Evidence.id == rel.evidence_id).first()
            assert evidence is not None
            assert "[DEMONSTRATION EVIDENCE]" in evidence.snippet
            assert evidence.document is not None
            assert "[DEMONSTRATION SAMPLE]" in evidence.document.raw_text


def test_seed_idempotency(isolated_engine):
    """Verifies executing seed_database twice leaves record counts completely unchanged."""
    first_run = seed_database(target_engine=isolated_engine)
    assert first_run is True

    with Session(isolated_engine) as session:
        suppliers_count_1 = session.query(Supplier).count()
        relationships_count_1 = session.query(Relationship).count()
        materials_count_1 = session.query(Material).count()

    # Second run should be idempotent and make no modifications
    second_run = seed_database(target_engine=isolated_engine)
    assert second_run is False

    with Session(isolated_engine) as session:
        assert session.query(Supplier).count() == suppliers_count_1
        assert session.query(Relationship).count() == relationships_count_1
        assert session.query(Material).count() == materials_count_1


def test_reset_functionality(isolated_engine):
    """Verifies --reset with force=True drops, recreates, and reseeds cleanly."""
    seed_database(target_engine=isolated_engine)

    # Force reset on isolated test engine
    reset_run = seed_database(target_engine=isolated_engine, reset=True, force=True)
    assert reset_run is True

    with Session(isolated_engine) as session:
        assert session.query(Supplier).count() == 7
        assert session.query(Relationship).count() == 6
        assert session.query(Material).count() == 5
