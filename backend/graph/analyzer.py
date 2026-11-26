"""
Dependency analyzer module for detecting hidden vulnerabilities in multi-tier supplier networks.
Conforms to project-docs/ARCHITECTURE.md Section 3.5 and project-docs/API_SPEC.md Section 4.5.
Implements ONLY:
- shared_upstream_supplier
- single_source_material
"""

from typing import List, Set, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.db import (
    Supplier,
    Relationship,
    Material,
    ProductionLine,
    LineRequirement,
)
from backend.graph.service import GraphService
from backend.models.schemas import (
    DependencyItem,
    DependencySupplierRef,
    DependencyMaterialRef,
)


class DependencyAnalyzer:
    """
    Analyzes the multi-tier supplier network to detect hidden dependency patterns
    and single-source vulnerabilities.
    """

    @staticmethod
    def analyze(db: Session, graph_service: GraphService) -> List[DependencyItem]:
        """
        Runs dependency detection across active suppliers and approved relationships:
        1. shared_upstream_supplier: Tier 2+ supplier whose downstream reach feeds >= 2 Tier 1 suppliers.
        2. single_source_material: Material with exactly one supplier among approved relationships.
        """
        items: List[DependencyItem] = []
        dep_index = 1

        # Build mapping of Tier 1 suppliers to production lines they feed
        tier1_to_lines: Dict[int, List[str]] = {}
        mfg_id = graph_service.manufacturer_id

        # Query all active production lines and their required materials
        lines_with_reqs = (
            db.query(ProductionLine.name, LineRequirement.material_id)
            .join(LineRequirement, ProductionLine.id == LineRequirement.line_id)
            .all()
        )
        mat_to_lines: Dict[int, List[str]] = {}
        for line_name, mat_id in lines_with_reqs:
            mat_to_lines.setdefault(mat_id, []).append(line_name)

        # Tier 1 relationships delivering to the manufacturer
        if mfg_id is not None:
            tier1_rels = (
                db.query(Relationship.supplier_id, Relationship.material_id)
                .filter(
                    Relationship.status == "approved",
                    Relationship.buyer_id == mfg_id,
                )
                .all()
            )
            for s_id, mat_id in tier1_rels:
                lines = mat_to_lines.get(mat_id, [])
                for line in lines:
                    if line not in tier1_to_lines.setdefault(s_id, []):
                        tier1_to_lines[s_id].append(line)

        # ---------------------------------------------------------------------
        # 1. shared_upstream_supplier
        # Tier 2+ supplier whose downstream descendants include >= 2 distinct Tier 1 suppliers
        # ---------------------------------------------------------------------
        active_suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
        supplier_map = {s.id: s for s in active_suppliers}

        for s in active_suppliers:
            node_data = graph_service.get_node_data(s.id)
            s_tier = node_data.get("tier") if node_data else None
            # Only consider Tier 2 or deeper
            if s_tier is not None and s_tier >= 2:
                # Direct out-degree (direct downstream buyers) must be >= 2
                direct_buyers = graph_service.get_direct_buyers(s.id)
                if len(direct_buyers) < 2:
                    continue

                # Downstream descendants must include at least two distinct Tier 1 suppliers
                descendants = graph_service.get_downstream_descendants(s.id)
                tier1_descendants = []
                for d_id in sorted(descendants):
                    d_node = graph_service.get_node_data(d_id)
                    if d_node and d_node.get("tier") == 1:
                        tier1_descendants.append(d_id)

                if len(tier1_descendants) >= 2:
                    affected_tier1_names = [supplier_map[tid].name for tid in tier1_descendants if tid in supplier_map]

                    # Collect affected lines fed by these Tier 1 suppliers
                    affected_lines_set: Set[str] = set()
                    for tid in tier1_descendants:
                        for l_name in tier1_to_lines.get(tid, []):
                            affected_lines_set.add(l_name)
                    affected_lines = sorted(affected_lines_set)

                    desc_str = (
                        f"Feeds {len(affected_tier1_names)} Tier 1 suppliers "
                        f"({', '.join(affected_tier1_names)}), which supply "
                        f"{len(affected_lines)} production line{'s' if len(affected_lines) != 1 else ''}."
                    )

                    items.append(
                        DependencyItem(
                            id=f"dep-{dep_index}",
                            type="shared_upstream_supplier",
                            supplier=DependencySupplierRef(
                                id=s.id,
                                name=s.name,
                                tier=s_tier,
                            ),
                            material=None,
                            description=desc_str,
                            affected_tier1=affected_tier1_names,
                            affected_lines=affected_lines,
                            severity="high",
                        )
                    )
                    dep_index += 1

        # ---------------------------------------------------------------------
        # 2. single_source_material
        # Approved raw materials supplied by exactly 1 unique active supplier at Tier 2+
        # ---------------------------------------------------------------------
        raw_supplying_records = (
            db.query(Relationship.material_id, Relationship.supplier_id)
            .join(Supplier, Relationship.supplier_id == Supplier.id)
            .join(Material, Relationship.material_id == Material.id)
            .filter(
                Relationship.status == "approved",
                Supplier.is_active == True,
                Material.material_type == "raw",
            )
            .distinct()
            .all()
        )

        # Group distinct active approved suppliers with computed tier >= 2 by material_id
        raw_mat_tier2_suppliers: Dict[int, Set[int]] = {}
        for mat_id, supp_id in raw_supplying_records:
            node_data = graph_service.get_node_data(supp_id)
            s_tier = node_data.get("tier") if node_data else None
            if s_tier is not None and s_tier >= 2:
                raw_mat_tier2_suppliers.setdefault(mat_id, set()).add(supp_id)

        # Flag a material only when exactly one distinct Tier 2+ supplier exists
        for mat_id in sorted(raw_mat_tier2_suppliers.keys()):
            tier2_supp_ids = raw_mat_tier2_suppliers[mat_id]
            if len(tier2_supp_ids) != 1:
                continue

            supp_id = next(iter(tier2_supp_ids))
            supp = supplier_map.get(supp_id) or db.query(Supplier).filter(Supplier.id == supp_id).first()
            mat = db.query(Material).filter(Material.id == mat_id).first()
            if not mat or not supp:
                continue

            node_data = graph_service.get_node_data(supp.id)
            s_tier = node_data.get("tier") if node_data else None

            # Collect affected lines that require this material directly or through Tier 1
            affected_lines = sorted(set(mat_to_lines.get(mat_id, [])))
            # If not directly required by a line, check if the supplier reaches Tier 1 suppliers that supply lines
            if not affected_lines:
                descendants = graph_service.get_downstream_descendants(supp.id)
                for d_id in descendants:
                    d_node = graph_service.get_node_data(d_id)
                    if d_node and d_node.get("tier") == 1:
                        for l_name in tier1_to_lines.get(d_id, []):
                            if l_name not in affected_lines:
                                affected_lines.append(l_name)
                affected_lines = sorted(affected_lines)

            # Affected Tier 1 suppliers
            affected_tier1: List[str] = []
            if s_tier == 1:
                affected_tier1 = [supp.name]
            else:
                descendants = graph_service.get_downstream_descendants(supp.id)
                for d_id in sorted(descendants):
                    d_node = graph_service.get_node_data(d_id)
                    if d_node and d_node.get("tier") == 1 and d_id in supplier_map:
                        affected_tier1.append(supplier_map[d_id].name)

            desc_str = f"Only one supplier of {mat.name} on this chain."

            items.append(
                DependencyItem(
                    id=f"dep-{dep_index}",
                    type="single_source_material",
                    supplier=DependencySupplierRef(
                        id=supp.id,
                        name=supp.name,
                        tier=s_tier,
                    ),
                    material=DependencyMaterialRef(
                        id=mat.id,
                        name=mat.name,
                    ),
                    description=desc_str,
                    affected_tier1=affected_tier1 if affected_tier1 else None,
                    affected_lines=affected_lines if affected_lines else None,
                    severity="high",
                )
            )
            dep_index += 1

        return items

    @staticmethod
    def get_supplier_vulnerability_flags(
        db: Session, graph_service: GraphService
    ) -> Dict[int, List[str]]:
        """
        Returns a mapping of supplier_id -> list of flags, e.g.
        ['hidden_dependency', 'single_source'].
        """
        flags_map: Dict[int, List[str]] = {}
        deps = DependencyAnalyzer.analyze(db, graph_service)

        for dep in deps:
            if dep.supplier is None:
                continue
            sid = dep.supplier.id
            if sid not in flags_map:
                flags_map[sid] = []

            if dep.type == "shared_upstream_supplier" and "hidden_dependency" not in flags_map[sid]:
                flags_map[sid].append("hidden_dependency")
            elif dep.type == "single_source_material" and "single_source" not in flags_map[sid]:
                flags_map[sid].append("single_source")

        for sid in flags_map:
            flags_map[sid].sort()

        return flags_map

