"""
Idempotent, non-destructive database initialization and seeding script for TierLens AI.
Usage:
    python -m backend.seed          # Initializes and seeds if empty (idempotent)
    python -m backend.seed --reset  # Prompts confirmation and recreates tables
"""

import sys
from sqlalchemy.orm import Session
from backend.database import engine, init_db, Base
from backend.models.db import (
    Document,
    Supplier,
    SupplierAlias,
    Material,
    SupplierMaterial,
    Evidence,
    Relationship,
    RelationshipEvidence,
    Plant,
    Product,
    ProductionLine,
    LineRequirement,
    DisruptionEvent,
)
from data.sample_data import (
    SAMPLE_DOCUMENTS,
    SAMPLE_SUPPLIERS,
    SAMPLE_ALIASES,
    SAMPLE_MATERIALS,
    SAMPLE_SUPPLIER_MATERIALS,
    SAMPLE_PLANTS,
    SAMPLE_PRODUCTS,
    SAMPLE_PRODUCTION_LINES,
    SAMPLE_LINE_REQUIREMENTS,
    SAMPLE_EVIDENCE,
    SAMPLE_RELATIONSHIPS,
    SAMPLE_EVENTS,
)


def seed_database(target_engine=None, reset=False, force=False):
    """
    Seeds the target database with synthetic automotive demonstration data.
    - If reset is True, drops all existing tables after user confirmation (or force=True).
    - If reset is False, runs idempotently: skips seeding if suppliers table is populated.
    - relationships.tier is left as NULL; tier computation belongs to the graph service.
    """
    eng = target_engine or engine

    if reset:
        if not force:
            print("=" * 68)
            print("WARNING: --reset will PERMANENTLY DROP all 17 tables and erase all data!")
            print("=" * 68)
            confirmation = input("Type 'YES' to confirm and proceed: ")
            if confirmation.strip() != "YES":
                print("Reset aborted by user. Database unchanged.")
                return False
        Base.metadata.drop_all(bind=eng)
        print("Dropped all existing tables.")

    # Initialize tables and the review_queue view
    init_db(target_engine=eng)

    with Session(eng) as session:
        # Idempotency check: if suppliers exist and not resetting, do nothing
        existing_count = session.query(Supplier).count()
        if existing_count > 0 and not reset:
            print(f"Database already contains {existing_count} supplier records.")
            print("Idempotent check passed; no modifications made.")
            return False

        print("Seeding synthetic automotive demonstration dataset...")

        # 1. Documents
        doc_map = {}
        for doc_data in SAMPLE_DOCUMENTS:
            doc = Document(**doc_data)
            session.add(doc)
            session.flush()
            doc_map[doc.filename] = doc.id

        # 2. Suppliers
        sup_map = {}
        for sup_data in SAMPLE_SUPPLIERS:
            sup = Supplier(**sup_data)
            session.add(sup)
            session.flush()
            sup_map[sup.name] = sup.id

        # 3. Aliases
        for alias_data in SAMPLE_ALIASES:
            sup_id = sup_map[alias_data["supplier_name"]]
            alias = SupplierAlias(
                supplier_id=sup_id,
                alias=alias_data["alias"],
                match_score=alias_data.get("match_score"),
                resolved_by=alias_data.get("resolved_by"),
            )
            session.add(alias)

        # 4. Materials
        mat_map = {}
        for mat_data in SAMPLE_MATERIALS:
            mat = Material(**mat_data)
            session.add(mat)
            session.flush()
            mat_map[mat.name] = mat.id

        # 5. Supplier Materials (Capabilities)
        for sm_data in SAMPLE_SUPPLIER_MATERIALS:
            sm = SupplierMaterial(
                supplier_id=sup_map[sm_data["supplier_name"]],
                material_id=mat_map[sm_data["material_name"]],
                capacity_per_month=sm_data.get("capacity_per_month"),
                typical_lead_time_days=sm_data.get("typical_lead_time_days"),
                is_qualified=sm_data.get("is_qualified", False),
            )
            session.add(sm)

        # 6. Plants
        plant_map = {}
        for plant_data in SAMPLE_PLANTS:
            plant = Plant(
                manufacturer_id=sup_map[plant_data["manufacturer_name"]],
                name=plant_data["name"],
                location=plant_data.get("location"),
            )
            session.add(plant)
            session.flush()
            plant_map[plant.name] = plant.id

        # 7. Products
        prod_map = {}
        for prod_data in SAMPLE_PRODUCTS:
            prod = Product(**prod_data)
            session.add(prod)
            session.flush()
            prod_map[prod.name] = prod.id

        # 8. Production Lines
        line_map = {}
        for line_data in SAMPLE_PRODUCTION_LINES:
            line = ProductionLine(
                plant_id=plant_map[line_data["plant_name"]],
                product_id=prod_map[line_data["product_name"]],
                name=line_data["name"],
                units_per_day=line_data["units_per_day"],
                daily_revenue=line_data.get("daily_revenue"),
            )
            session.add(line)
            session.flush()
            line_map[line.name] = line.id

        # 9. Line Requirements
        for req_data in SAMPLE_LINE_REQUIREMENTS:
            req = LineRequirement(
                line_id=line_map[req_data["line_name"]],
                material_id=mat_map[req_data["material_name"]],
                qty_per_day=req_data["qty_per_day"],
                criticality=req_data.get("criticality", "high"),
                safety_stock_days=req_data.get("safety_stock_days", 0),
            )
            session.add(req)

        # 10. Evidence records
        evidence_by_rel = {}
        for ev_data in SAMPLE_EVIDENCE:
            doc_id = doc_map[ev_data["document_filename"]]
            evidence = Evidence(
                document_id=doc_id,
                page=ev_data.get("page"),
                chunk_index=ev_data.get("chunk_index"),
                snippet=ev_data["snippet"],
                llm_confidence=ev_data.get("llm_confidence"),
            )
            session.add(evidence)
            session.flush()
            rel_key = ev_data.get("rel_key")
            if rel_key:
                evidence_by_rel[rel_key] = evidence.id

        # 11. Relationships
        # NOTE: tier is intentionally None (NULL) per DATABASE_SCHEMA.md Section 6.
        for rel_data in SAMPLE_RELATIONSHIPS:
            sup_id = sup_map[rel_data["supplier_name"]]
            buyer_id = sup_map[rel_data["buyer_name"]]
            mat_id = mat_map[rel_data["material_name"]]
            rel_key = (rel_data["supplier_name"], rel_data["buyer_name"], rel_data["material_name"])
            ev_id = evidence_by_rel.get(rel_key)

            rel = Relationship(
                supplier_id=sup_id,
                buyer_id=buyer_id,
                material_id=mat_id,
                tier=None,  # Derived later by graph service
                lead_time_days=rel_data.get("lead_time_days"),
                share_pct=rel_data.get("share_pct"),
                inventory_days=rel_data.get("inventory_days", 0),
                quantity_per_month=rel_data.get("quantity_per_month"),
                confidence=rel_data.get("confidence"),
                status=rel_data.get("status", "pending"),
                evidence_id=ev_id,
            )
            session.add(rel)
            session.flush()

            # 12. RelationshipEvidence junction table link
            if ev_id:
                rel_ev = RelationshipEvidence(
                    relationship_id=rel.id,
                    evidence_id=ev_id,
                )
                session.add(rel_ev)

        # 13. Disruption Events
        for ev_data in SAMPLE_EVENTS:
            event = DisruptionEvent(
                supplier_id=sup_map[ev_data["supplier_name"]],
                event_type=ev_data["event_type"],
                severity=ev_data["severity"],
                start_date=ev_data["start_date"],
                expected_duration_days=ev_data.get("expected_duration_days"),
                description=ev_data.get("description"),
                source=ev_data.get("source"),
                is_simulated=ev_data.get("is_simulated", True),
            )
            session.add(event)

        session.commit()
        print("Database successfully seeded with synthetic automotive demonstration data.")
        return True


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    force_flag = "--force" in sys.argv
    seed_database(reset=reset_flag, force=force_flag)
