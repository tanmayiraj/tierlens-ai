"""
Comprehensive test suite for Supplier and Material Entity Resolution Engine (Milestone 4: Step 4.2).
Validates multi-stage matching, RapidFuzz thresholding, ambiguity detection, short-name protection,
material type inference, alias metadata tracking, and transaction rollback safety.
All tests run against isolated temporary SQLite databases.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.database import init_db
from backend.models.db import Supplier, SupplierAlias, Material
from backend.services.entity_resolver import (
    EntityResolver,
    normalize_company_name,
    normalize_material_name,
    infer_material_type,
    infer_material_category,
    ResolutionResult,
)


@pytest.fixture
def db_session(tmp_path):
    """
    Creates an isolated temporary SQLite database and yields an active SQLAlchemy Session.
    Guarantees that tierlens.db is never touched.
    """
    db_file = tmp_path / "test_entity_resolution.db"
    test_db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(target_engine=engine)
    session = Session(bind=engine)

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def populated_session(db_session: Session):
    """Populates the isolated test database with canonical suppliers, aliases, and materials."""
    # 1. Manufacturer Anchor
    mfg = Supplier(name="AutoMotive Corp", entity_type="manufacturer", base_risk=0.0, is_active=True)
    db_session.add(mfg)
    db_session.flush()

    # 2. Suppliers
    s1 = Supplier(name="GreenLatex Pvt Ltd", entity_type="supplier", country="India", region="South Asia", base_risk=35.0)
    s2 = Supplier(name="RubberCore Industries", entity_type="supplier", country="Malaysia", region="Southeast Asia", base_risk=28.0)
    s3 = Supplier(name="TyreWorks Ltd", entity_type="supplier", country="Vietnam", region="Southeast Asia", base_risk=20.0)
    s4 = Supplier(name="GripSeal Components", entity_type="supplier", country="India", region="South Asia", base_risk=15.0)
    s5 = Supplier(name="PetroChem Asia", entity_type="supplier", country="Singapore", region="Southeast Asia", base_risk=22.0)
    s6 = Supplier(name="3M Company", entity_type="supplier", country="USA", region="North America", base_risk=10.0)

    db_session.add_all([s1, s2, s3, s4, s5, s6])
    db_session.flush()

    # 3. Aliases
    a1 = SupplierAlias(supplier_id=s1.id, alias="GreenLatex", match_score=0.95, resolved_by="rule")
    a2 = SupplierAlias(supplier_id=s2.id, alias="RubberCore", match_score=0.95, resolved_by="rule")
    a3 = SupplierAlias(supplier_id=s3.id, alias="TyreWorks", match_score=0.95, resolved_by="rule")
    a4 = SupplierAlias(supplier_id=s4.id, alias="GripSeal", match_score=0.95, resolved_by="rule")

    db_session.add_all([a1, a2, a3, a4])
    db_session.flush()

    # 4. Materials
    m1 = Material(name="Natural Latex", material_type="raw", unit="MT", category="rubber")
    m2 = Material(name="Carbon Black", material_type="raw", unit="MT", category="chemicals")
    m3 = Material(name="Processed Rubber", material_type="raw", unit="MT", category="rubber")
    m4 = Material(name="Rubber Seals", material_type="part", unit="units", category="rubber")
    m5 = Material(name="Tyres", material_type="assembly", unit="units", category="automotive_components")

    db_session.add_all([m1, m2, m3, m4, m5])
    db_session.commit()

    return db_session


# =============================================================================
# Normalization Helper Unit Tests
# =============================================================================

def test_normalize_company_name():
    """Verifies that corporate legal tokens, punctuation, and casing are cleaned properly."""
    assert normalize_company_name("GreenLatex Pvt Ltd") == "greenlatex"
    assert normalize_company_name("RubberCore Industries") == "rubbercore industries"
    assert normalize_company_name("AutoMotive Corp.") == "automotive"
    assert normalize_company_name("TyreWorks, Ltd.") == "tyreworks"
    assert normalize_company_name("GripSeal Components") == "gripseal components"
    assert normalize_company_name("PetroChem Asia & Co.") == "petrochem asia"
    assert normalize_company_name("ABC Rubber Pvt Ltd") == "abc rubber"
    assert normalize_company_name("3M Company") == "3m"

    # Edge cases: short names and empty inputs
    assert normalize_company_name("3M") == "3m"
    assert normalize_company_name("Company") == "company"  # Does not strip if only word
    assert normalize_company_name("") == ""
    assert normalize_company_name("   ") == ""


def test_normalize_material_name():
    """Verifies whitespace, punctuation, and casing normalization for materials."""
    assert normalize_material_name("Natural Latex") == "natural latex"
    assert normalize_material_name("  natural   latex  ") == "natural latex"
    assert normalize_material_name("Rubber Seals - Grade A") == "rubber seals grade a"
    assert normalize_material_name("") == ""


# =============================================================================
# Supplier Resolution Tests
# =============================================================================

def test_resolve_exact_canonical_name(populated_session: Session):
    """Verifies Stage 1: Exact canonical supplier name match."""
    resolver = EntityResolver()
    res = resolver.resolve_supplier(populated_session, "GreenLatex Pvt Ltd")

    assert res.is_resolved is True
    assert res.match_type == "exact"
    assert res.match_score == 1.0
    assert res.canonical_name == "GreenLatex Pvt Ltd"
    assert res.is_new is False

    # Case-insensitive check
    res_lower = resolver.resolve_supplier(populated_session, "greenlatex pvt ltd")
    assert res_lower.match_type == "exact"
    assert res_lower.canonical_name == "GreenLatex Pvt Ltd"


def test_resolve_exact_alias(populated_session: Session):
    """Verifies Stage 2: Exact alias lookup from supplier_aliases."""
    resolver = EntityResolver()
    res = resolver.resolve_supplier(populated_session, "GreenLatex")

    assert res.is_resolved is True
    assert res.match_type == "alias"
    assert res.canonical_name == "GreenLatex Pvt Ltd"
    assert res.match_score == pytest.approx(0.95)
    assert res.is_new is False


def test_resolve_legal_suffix_normalization(populated_session: Session):
    """Verifies Stage 3: Normalization stripping legal tokens and persisting original alias."""
    resolver = EntityResolver()
    # "RubberCore, Inc." does not exist as an alias yet, but normalizes to "rubbercore"
    res = resolver.resolve_supplier(populated_session, "RubberCore, Inc.")

    assert res.is_resolved is True
    assert res.match_type == "normalized"
    assert res.match_score == 1.0
    assert res.canonical_name == "RubberCore Industries"
    assert res.is_new is False

    # Verify that "RubberCore, Inc." was saved into supplier_aliases
    saved_alias = populated_session.query(SupplierAlias).filter_by(alias="RubberCore, Inc.").first()
    assert saved_alias is not None
    assert saved_alias.supplier_id == res.entity_id
    assert saved_alias.resolved_by == "rule"


def test_resolve_fuzzy_above_90_percent(populated_session: Session):
    """Verifies Stage 4: RapidFuzz token_sort_ratio >= 90% threshold."""
    resolver = EntityResolver()
    # Minor typo in TyreWorks: "TyreWorkss Ltd"
    res = resolver.resolve_supplier(populated_session, "TyreWorkss Ltd")

    assert res.is_resolved is True
    assert res.match_type == "fuzzy"
    assert res.match_score >= 0.90
    assert res.canonical_name == "TyreWorks Ltd"
    assert res.is_new is False
    assert res.resolved_by == "fuzzy"

    # Verify new alias was added with fuzzy metadata
    saved_alias = populated_session.query(SupplierAlias).filter_by(alias="TyreWorkss Ltd").first()
    assert saved_alias is not None
    assert saved_alias.resolved_by == "fuzzy"
    assert saved_alias.match_score == res.match_score


def test_different_suppliers_below_threshold(populated_session: Session):
    """Verifies that distinctly different suppliers (< 90%) are not falsely merged."""
    resolver = EntityResolver()
    # "TyrePlus Inc" shares root context with "TyreWorks Ltd", but is a distinct company
    res = resolver.resolve_supplier(populated_session, "TyrePlus Inc", allow_create=False)

    assert res.is_resolved is False
    assert res.match_type == "unresolved"
    assert res.entity_id is None


def test_descriptor_separation_acme(populated_session: Session):
    """
    Regression test: Verifies that removing business descriptors from legal tokens
    prevents 'Acme Components Ltd' from automatically matching 'Acme Industries Ltd'.
    """
    acme_ind = Supplier(name="Acme Industries Ltd", entity_type="supplier", base_risk=12.0)
    populated_session.add(acme_ind)
    populated_session.flush()

    resolver = EntityResolver()

    # Query 'Acme Components Ltd' with allow_create=False must not match 'Acme Industries Ltd'
    res_no_create = resolver.resolve_supplier(populated_session, "Acme Components Ltd", allow_create=False)
    assert res_no_create.is_resolved is False
    assert res_no_create.match_type == "unresolved"
    assert res_no_create.entity_id is None

    # With allow_create=True, it creates a new distinct supplier rather than merging
    res_create = resolver.resolve_supplier(populated_session, "Acme Components Ltd", allow_create=True)
    assert res_create.is_resolved is True
    assert res_create.is_new is True
    assert res_create.canonical_name == "Acme Components Ltd"
    assert res_create.entity_id != acme_ind.id

    # Count distinct Acme suppliers in DB
    acme_count = populated_session.query(Supplier).filter(Supplier.name.ilike("Acme%")).count()
    assert acme_count == 2


def test_existing_aliases_rubbercore_and_gripseal(populated_session: Session):
    """
    Regression test: Verifies that 'RubberCore Industries' and 'GripSeal Components'
    continue to resolve accurately through their established aliases 'RubberCore' and 'GripSeal'.
    """
    resolver = EntityResolver()

    # 1. RubberCore alias resolution
    res_rc_alias = resolver.resolve_supplier(populated_session, "RubberCore")
    assert res_rc_alias.is_resolved is True
    assert res_rc_alias.match_type == "alias"
    assert res_rc_alias.canonical_name == "RubberCore Industries"

    # 2. RubberCore exact resolution
    res_rc_exact = resolver.resolve_supplier(populated_session, "RubberCore Industries")
    assert res_rc_exact.is_resolved is True
    assert res_rc_exact.match_type == "exact"
    assert res_rc_exact.canonical_name == "RubberCore Industries"

    # 3. GripSeal alias resolution
    res_gs_alias = resolver.resolve_supplier(populated_session, "GripSeal")
    assert res_gs_alias.is_resolved is True
    assert res_gs_alias.match_type == "alias"
    assert res_gs_alias.canonical_name == "GripSeal Components"

    # 4. GripSeal exact resolution
    res_gs_exact = resolver.resolve_supplier(populated_session, "GripSeal Components")
    assert res_gs_exact.is_resolved is True
    assert res_gs_exact.match_type == "exact"
    assert res_gs_exact.canonical_name == "GripSeal Components"


def test_ambiguous_fuzzy_matching(populated_session: Session):
    """
    Verifies that if two candidate suppliers score >= 85% with less than 5% difference,
    the match is rejected as ambiguous and never automatically merged.
    """
    # Add two closely named competing suppliers
    supp_a = Supplier(name="Apex Rubber Solutions Ltd", entity_type="supplier", base_risk=10.0)
    supp_b = Supplier(name="Apex Rubber Solutionz Ltd", entity_type="supplier", base_risk=10.0)
    populated_session.add_all([supp_a, supp_b])
    populated_session.flush()

    resolver = EntityResolver()
    # "Apex Rubber Solution Ltd" scores 97.5% against both (diff < 5%)
    res = resolver.resolve_supplier(populated_session, "Apex Rubber Solution Ltd", allow_create=False)

    assert res.is_ambiguous is True
    assert res.match_type == "ambiguous"
    assert res.entity_id is None
    assert len(res.candidate_names) == 2
    assert "Apex Rubber Solutions Ltd" in res.candidate_names
    assert "Apex Rubber Solutionz Ltd" in res.candidate_names

    # Even with allow_create=True, ambiguous names must not auto-create
    res_create = resolver.resolve_supplier(populated_session, "Apex Rubber Solution Ltd", allow_create=True)
    assert res_create.is_ambiguous is True
    assert res_create.entity_id is None

    # resolve_or_create_supplier should raise ValueError on ambiguity
    with pytest.raises(ValueError, match="ambiguous match"):
        resolver.resolve_or_create_supplier(populated_session, "Apex Rubber Solution Ltd")


def test_short_name_protection(populated_session: Session):
    """Verifies that short names (<= 3 chars) do not trigger loose fuzzy matches."""
    resolver = EntityResolver()
    # "3M Company" has root "3m" (len 2). A query like "2M" or "4M" must not match "3M"
    res = resolver.resolve_supplier(populated_session, "2M", allow_create=False)
    assert res.is_resolved is False
    assert res.match_type == "unresolved"

    # Exact short name "3M" matches via normalized / alias
    res_exact = resolver.resolve_supplier(populated_session, "3M")
    assert res_exact.is_resolved is True
    assert res_exact.canonical_name == "3M Company"


def test_new_supplier_creation(populated_session: Session):
    """Verifies that genuinely unknown suppliers are created with documented defaults when allow_create=True."""
    resolver = EntityResolver()
    res = resolver.resolve_supplier(populated_session, "Starlight Minerals Inc", allow_create=True)

    assert res.is_resolved is True
    assert res.match_type == "created"
    assert res.is_new is True
    assert res.canonical_name == "Starlight Minerals Inc"

    # Verify supplier record in DB
    supp = populated_session.query(Supplier).filter_by(id=res.entity_id).first()
    assert supp is not None
    assert supp.name == "Starlight Minerals Inc"
    assert supp.entity_type == "supplier"
    assert supp.base_risk == 0.0
    assert supp.is_active is True


def test_no_duplicate_supplier_creation(populated_session: Session):
    """Verifies that calling resolve_supplier or resolve_or_create_supplier repeatedly creates no duplicates."""
    resolver = EntityResolver()
    res1 = resolver.resolve_supplier(populated_session, "Delta Composites Co.", allow_create=True)
    assert res1.is_new is True

    # Second call should match the existing record
    res2 = resolver.resolve_supplier(populated_session, "Delta Composites Co.", allow_create=True)
    assert res2.is_new is False
    assert res2.entity_id == res1.entity_id

    # Third call with resolve_or_create_supplier
    supp = resolver.resolve_or_create_supplier(populated_session, "Delta Composites Co.")
    assert supp.id == res1.entity_id

    # Count records in database
    count = populated_session.query(Supplier).filter(Supplier.name.ilike("Delta Composites%")).count()
    assert count == 1


# =============================================================================
# Material Resolution Tests
# =============================================================================

def test_resolve_exact_material(populated_session: Session):
    """Verifies exact and case-insensitive matching for canonical materials."""
    resolver = EntityResolver()
    res = resolver.resolve_material(populated_session, "Natural Latex")

    assert res.is_resolved is True
    assert res.match_type == "exact"
    assert res.canonical_name == "Natural Latex"

    res_lower = resolver.resolve_material(populated_session, "natural latex")
    assert res_lower.is_resolved is True
    assert res_lower.match_type == "exact"


def test_resolve_normalized_material(populated_session: Session):
    """Verifies material normalization matching (whitespace and casing)."""
    resolver = EntityResolver()
    res = resolver.resolve_material(populated_session, "  carbon   black  ")
    assert res.is_resolved is True
    assert res.match_type == "normalized"
    assert res.canonical_name == "Carbon Black"


def test_resolve_fuzzy_material(populated_session: Session):
    """Verifies fuzzy matching for materials with >= 90% threshold."""
    resolver = EntityResolver()
    # Minor spelling variant: "Natural Latexx" -> "Natural Latex" (score > 0.90)
    res = resolver.resolve_material(populated_session, "Natural Latexx")
    assert res.is_resolved is True
    assert res.match_type == "fuzzy"
    assert res.match_score >= 0.90
    assert res.canonical_name == "Natural Latex"


def test_create_new_material_with_unit(populated_session: Session):
    """Verifies new material creation with unit preservation."""
    resolver = EntityResolver()
    res = resolver.resolve_material(
        populated_session,
        "Silicone Sealant Compound",
        allow_create=True,
        unit="liters",
    )

    assert res.is_resolved is True
    assert res.is_new is True
    assert res.match_type == "created"

    mat = populated_session.query(Material).filter_by(id=res.entity_id).first()
    assert mat is not None
    assert mat.name == "Silicone Sealant Compound"
    assert mat.unit == "liters"
    assert mat.material_type == "raw"
    assert mat.category == "chemicals"


def test_material_type_inference():
    """Verifies that material_type is inferred accurately according to system specifications."""
    # Assembly: assemblies, modules, systems
    assert infer_material_type("Steering Column Assembly") == "assembly"
    assert infer_material_type("Power Control Module") == "assembly"
    assert infer_material_type("Hydraulic Braking System") == "assembly"

    # Part: components, seals, gaskets, wires, sensors, valves
    assert infer_material_type("High Pressure Valve") == "part"
    assert infer_material_type("Viton O-Ring Seal") == "part"
    assert infer_material_type("Engine Cylinder Gasket") == "part"
    assert infer_material_type("Copper Wire Harness") == "part"
    assert infer_material_type("Wheel Speed Sensor") == "part"
    assert infer_material_type("Chassis Suspension Component") == "part"

    # Raw: default
    assert infer_material_type("Natural Latex") == "raw"
    assert infer_material_type("Carbon Black") == "raw"
    assert infer_material_type("Hot Rolled Steel Sheet") == "raw"
    assert infer_material_type("Polymer Pellets") == "raw"


def test_infer_material_category():
    """Verifies material category inference from keyword heuristics."""
    assert infer_material_category("Natural Latex Rubber") == "rubber"
    assert infer_material_category("Carbon Black Powder") == "chemicals"
    assert infer_material_category("Cold Rolled Steel") == "metals"
    assert infer_material_category("Optical Sensor Wire") == "electronics"
    assert infer_material_category("Generic Packing Box") is None


# =============================================================================
# Transaction Safety & Rollback Tests
# =============================================================================

def test_transaction_rollback_safety(populated_session: Session):
    """
    Verifies that all entity resolution operations respect transaction boundaries.
    Because the resolver calls flush() instead of commit(), rolling back the session
    cleanses all created suppliers, aliases, and materials without leaving orphaned rows.
    """
    resolver = EntityResolver()

    # Create supplier and material inside transaction
    res_supp = resolver.resolve_supplier(populated_session, "Temporary Vendor LLC", allow_create=True)
    res_mat = resolver.resolve_material(populated_session, "Temporary Rare Metal", allow_create=True)

    assert res_supp.is_new is True
    assert res_mat.is_new is True
    supp_id = res_supp.entity_id
    mat_id = res_mat.entity_id

    # Verify they exist in the uncommitted session
    assert populated_session.query(Supplier).filter_by(id=supp_id).first() is not None
    assert populated_session.query(Material).filter_by(id=mat_id).first() is not None

    # Roll back transaction
    populated_session.rollback()

    # Verify neither supplier, nor alias, nor material exists after rollback
    assert populated_session.query(Supplier).filter_by(id=supp_id).first() is None
    assert populated_session.query(Material).filter_by(id=mat_id).first() is None
    assert populated_session.query(SupplierAlias).filter_by(alias="Temporary Vendor LLC").first() is None
