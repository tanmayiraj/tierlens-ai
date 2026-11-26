"""
Risk Analysis Engine Service for TierLens AI (Milestone 6: TASK-017).
Conforms to project-docs/ARCHITECTURE.md Section 3.6, project-docs/PRD.md Section 10,
and project-docs/API_SPEC.md Section 4.6.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.db import (
    Supplier,
    Relationship,
    Material,
    ProductionLine,
    LineRequirement,
    SupplierMaterial,
    DisruptionEvent,
    Alert,
    AlertAffectedNode,
)
from backend.graph.service import GraphService
from backend.graph.analyzer import DependencyAnalyzer


@dataclass
class AffectedNodeInfo:
    node_type: str  # 'supplier', 'material', 'line', 'product'
    node_id: int
    name: str
    path_depth: int
    days_to_impact: Optional[int]


@dataclass
class LineImpactInfo:
    line_id: int
    line_name: str
    days_to_impact: Optional[int]
    unbuffered_days: int
    daily_revenue: float
    revenue_at_risk: float


@dataclass
class RiskEvaluationResult:
    supplier_id: int
    event_id: int
    risk_score: float
    severity_label: str  # 'low', 'medium', 'high', 'critical'
    score_breakdown: Dict[str, float]
    days_to_impact: Optional[int]
    revenue_at_risk: float
    explanation: str
    affected_nodes: List[AffectedNodeInfo]
    affected_lines: List[LineImpactInfo]


class RiskEngine:
    """
    Evaluates multi-factor supply chain disruption risk, downstream impact,
    and revenue exposure.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or settings.RISK_WEIGHTS
        self.duration_benchmark = getattr(settings, "DURATION_BENCHMARK_DAYS", 37.5)

    @staticmethod
    def classify_severity(score: float) -> str:
        """
        Maps a 0–100 risk score to its severity label strictly per DESIGN_SYSTEM.md:
        - Low: 0–39 (score < 40.0)
        - Medium: 40–59 (40.0 <= score < 60.0)
        - High: 60–79 (60.0 <= score < 80.0)
        - Critical: 80–100 (score >= 80.0)
        """
        if score >= 80.0:
            return "critical"
        elif score >= 60.0:
            return "high"
        elif score >= 40.0:
            return "medium"
        else:
            return "low"

    def calculate_event_severity(self, event: DisruptionEvent) -> float:
        """
        Factor 1: Event Severity (Ceiling: 25.0)
        Base severity (severity / 5.0 * 20.0) + Duration (min(5.0, duration / 7.5))
        """
        sev = float(event.severity)
        base_score = (sev / 5.0) * 20.0

        duration = float(event.expected_duration_days or 0)
        # Scaled by 37.5 days benchmark (where 30 days gives 4.0 pts)
        dur_score = min(5.0, (duration / self.duration_benchmark) * 5.0)

        return round(base_score + dur_score, 1)

    def trace_downstream_impact(
        self,
        supplier_id: int,
        duration_days: int,
        db: Session,
        graph_service: GraphService,
    ) -> Tuple[List[AffectedNodeInfo], List[LineImpactInfo], Optional[int], float]:
        """
        Traverses approved supply relationships downstream from supplier_id to:
        1. Identify affected suppliers, materials, and production lines.
        2. Compute cumulative inventory buffer (days to impact) at each hop.
        3. Calculate line-by-line unbuffered days and INR revenue at risk.
        Zero unbuffered days -> revenue at risk is strictly 0.0.
        """
        if not graph_service.is_built:
            graph_service.rebuild(db)

        mfg_id = graph_service.manufacturer_id

        # Query all active production lines and their required materials
        lines_with_reqs = (
            db.query(ProductionLine, LineRequirement.material_id)
            .join(LineRequirement, ProductionLine.id == LineRequirement.line_id)
            .all()
        )
        # material_id -> list of (ProductionLine, qty_per_day)
        mat_to_lines: Dict[int, List[ProductionLine]] = {}
        for line_obj, mat_id in lines_with_reqs:
            mat_to_lines.setdefault(mat_id, []).append(line_obj)

        # Preload all active approved relationships
        approved_rels = (
            db.query(Relationship)
            .filter(Relationship.status == "approved")
            .all()
        )
        # supplier_id -> list of relationships
        supplier_rel_map: Dict[int, List[Relationship]] = {}
        for r in approved_rels:
            supplier_rel_map.setdefault(r.supplier_id, []).append(r)

        suppliers_by_id = {s.id: s for s in db.query(Supplier).all()}
        materials_by_id = {m.id: m for m in db.query(Material).all()}

        # BFS downstream traversal tracking (node_id, current_depth, cumulative_buffer)
        visited_suppliers: Dict[int, int] = {}  # supplier_id -> cumulative_buffer
        queue: List[Tuple[int, int, int]] = [(supplier_id, 0, 0)]

        affected_nodes: List[AffectedNodeInfo] = []
        affected_materials: Set[int] = set()
        line_impact_map: Dict[int, LineImpactInfo] = {}

        while queue:
            curr_supp_id, curr_depth, curr_buffer = queue.pop(0)

            # Find all outgoing approved supply edges
            outgoing = supplier_rel_map.get(curr_supp_id, [])
            for r in outgoing:
                buyer_id = r.buyer_id
                mat_id = r.material_id
                affected_materials.add(mat_id)

                # Hop buffer: buyer's on-hand inventory days of this material
                hop_buffer = r.inventory_days or 0
                cum_buffer = curr_buffer + hop_buffer
                next_depth = curr_depth + 1

                # If buyer is the manufacturer OEM
                if mfg_id is not None and buyer_id == mfg_id:
                    # When reaching OEM manufacturer lines:
                    # - If indirect upstream (curr_buffer > 0), line is impacted when the Tier 1 starves (curr_buffer).
                    # - If direct supplier disruption (curr_buffer == 0), line has direct relationship inventory_days.
                    line_buffer = curr_buffer if curr_buffer > 0 else (r.inventory_days or 0)

                    # Check which production lines consume this material
                    target_lines = mat_to_lines.get(mat_id, [])
                    for pline in target_lines:
                        # Existing buffer if reached through multiple paths
                        prev_line_info = line_impact_map.get(pline.id)
                        effective_buffer = (
                            min(prev_line_info.days_to_impact, line_buffer)
                            if prev_line_info and prev_line_info.days_to_impact is not None
                            else line_buffer
                        )

                        unbuffered_days = max(0, duration_days - effective_buffer)
                        daily_rev = float(pline.daily_revenue or 0.0)
                        line_rev_at_risk = (
                            daily_rev * unbuffered_days if unbuffered_days > 0 else 0.0
                        )

                        line_impact_map[pline.id] = LineImpactInfo(
                            line_id=pline.id,
                            line_name=pline.name,
                            days_to_impact=effective_buffer,
                            unbuffered_days=unbuffered_days,
                            daily_revenue=daily_rev,
                            revenue_at_risk=line_rev_at_risk,
                        )
                else:
                    # Downstream supplier node
                    if buyer_id not in visited_suppliers or cum_buffer < visited_suppliers[buyer_id]:
                        visited_suppliers[buyer_id] = cum_buffer
                        supp_obj = suppliers_by_id.get(buyer_id)
                        supp_name = supp_obj.name if supp_obj else f"Supplier #{buyer_id}"

                        affected_nodes.append(
                            AffectedNodeInfo(
                                node_type="supplier",
                                node_id=buyer_id,
                                name=supp_name,
                                path_depth=next_depth,
                                days_to_impact=cum_buffer,
                            )
                        )
                        queue.append((buyer_id, next_depth, cum_buffer))

        # Add affected production lines to affected_nodes list
        affected_lines_list = sorted(line_impact_map.values(), key=lambda l: l.line_id)
        for line_info in affected_lines_list:
            # path depth to line is depth from direct supplier + 1
            affected_nodes.append(
                AffectedNodeInfo(
                    node_type="line",
                    node_id=line_info.line_id,
                    name=line_info.line_name,
                    path_depth=3,  # OEM line depth
                    days_to_impact=line_info.days_to_impact,
                )
            )

        # Compute earliest line days to impact & total revenue at risk
        if affected_lines_list:
            earliest_line_impact = min(
                (l.days_to_impact for l in affected_lines_list if l.days_to_impact is not None),
                default=None,
            )
            # Total revenue at risk: sum of all line exposures
            total_revenue_at_risk = sum(l.revenue_at_risk for l in affected_lines_list)

            # If disruption is fully absorbed across all lines, revenue is strictly 0.0
            if all(l.unbuffered_days == 0 for l in affected_lines_list):
                total_revenue_at_risk = 0.0
                earliest_line_impact = None
        else:
            earliest_line_impact = None
            total_revenue_at_risk = 0.0

        return affected_nodes, affected_lines_list, earliest_line_impact, total_revenue_at_risk

    def calculate_criticality(
        self,
        supplier_id: int,
        affected_lines: List[LineImpactInfo],
        affected_nodes: List[AffectedNodeInfo],
        db: Session,
        graph_service: GraphService,
    ) -> float:
        """
        Factor 2: Criticality (Ceiling: 25.0)
        Lines reach (up to 15.0) + Tier 1 reach (up to 7.0) + Direct OEM coupling (up to 3.0)
        """
        total_lines_count = db.query(ProductionLine).count() or 1
        lines_reached_count = len(affected_lines)
        lines_score = (lines_reached_count / total_lines_count) * 15.0

        # Reach among Tier 1 suppliers
        affected_supplier_ids = {n.node_id for n in affected_nodes if n.node_type == "supplier"}
        active_suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()

        total_tier1 = 0
        reached_tier1 = 0
        for s in active_suppliers:
            node_data = graph_service.get_node_data(s.id)
            if node_data and node_data.get("tier") == 1:
                total_tier1 += 1
                if s.id in affected_supplier_ids or s.id == supplier_id:
                    reached_tier1 += 1

        tier1_score = (reached_tier1 / total_tier1 * 7.0) if total_tier1 > 0 else 0.0

        # Direct OEM Coupling: 3.0 if supplier is direct Tier 1; 0.0 if indirect (Tier 2+)
        s_tier = (graph_service.get_node_data(supplier_id) or {}).get("tier")
        direct_score = 3.0 if s_tier == 1 else 0.0

        return round(lines_score + tier1_score + direct_score, 1)

    def calculate_single_source_exposure(
        self,
        supplier_id: int,
        db: Session,
        graph_service: GraphService,
    ) -> float:
        """
        Factor 3: Single-Source Exposure (Ceiling: 25.0)
        Single source with no alt = 25.0
        Single source with uncontracted qualified alt = 20.0
        Multi-sourced with >= 70% concentration = 12.0
        Balanced multi-sourced = 5.0
        """
        flags_map = DependencyAnalyzer.get_supplier_vulnerability_flags(db, graph_service)
        supplier_flags = flags_map.get(supplier_id, [])

        is_single_source = "single_source" in supplier_flags
        is_shared_upstream = "hidden_dependency" in supplier_flags

        if is_single_source or is_shared_upstream:
            # Query materials delivered by this supplier
            supplied_materials = (
                db.query(Relationship.material_id)
                .filter(
                    Relationship.supplier_id == supplier_id,
                    Relationship.status == "approved",
                )
                .distinct()
                .all()
            )
            mat_ids = [m[0] for m in supplied_materials]

            # Check if any other supplier is qualified for any of these materials
            has_qualified_alt = (
                db.query(SupplierMaterial)
                .filter(
                    SupplierMaterial.material_id.in_(mat_ids),
                    SupplierMaterial.supplier_id != supplier_id,
                    SupplierMaterial.is_qualified == True,
                )
                .first()
            ) is not None

            if not has_qualified_alt:
                return 25.0
            else:
                return 20.0

        # Concentration check on active outgoing relationships
        high_share = (
            db.query(Relationship)
            .filter(
                Relationship.supplier_id == supplier_id,
                Relationship.status == "approved",
                Relationship.share_pct >= 70.0,
            )
            .first()
        )
        if high_share:
            return 12.0

        return 5.0

    def calculate_buffer_gap(
        self,
        duration_days: int,
        first_line_impact_days: Optional[int],
    ) -> float:
        """
        Factor 4: Buffer Gap (Ceiling: 15.0)
        Normalized by duration_days.
        Zero unbuffered gap -> 0.0 pts.
        """
        if first_line_impact_days is None or duration_days <= first_line_impact_days:
            return 0.0

        gap = duration_days - first_line_impact_days
        deficit_ratio = gap / float(duration_days) if duration_days > 0 else 0.0
        buffer_score = 15.0 * deficit_ratio
        return round(buffer_score, 1)

    def calculate_regional_risk(self, supplier_id: int, db: Session) -> float:
        """
        Factor 5: Regional Risk (Ceiling: 10.0)
        Scaled strictly from suppliers.base_risk (0 to 100).
        """
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        base_risk = float(supplier.base_risk or 0.0) if supplier else 0.0
        regional_score = 10.0 * (base_risk / 100.0)
        return round(regional_score, 1)

    def evaluate_event(
        self,
        event: DisruptionEvent,
        db: Session,
        graph_service: Optional[GraphService] = None,
    ) -> RiskEvaluationResult:
        """
        Runs complete risk and impact evaluation for a disruption event.
        """
        gs = graph_service or GraphService()
        if not gs.is_built:
            gs.rebuild(db)

        supplier = db.query(Supplier).filter(Supplier.id == event.supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier {event.supplier_id} not found")

        duration_days = int(event.expected_duration_days or 0)

        # 1. Downstream Traversal & Buffer Impact
        (
            affected_nodes,
            affected_lines,
            earliest_impact_days,
            total_rev_at_risk,
        ) = self.trace_downstream_impact(event.supplier_id, duration_days, db, gs)

        # 2. Compute 5 Factors
        score_event_sev = self.calculate_event_severity(event)
        score_crit = self.calculate_criticality(
            event.supplier_id, affected_lines, affected_nodes, db, gs
        )
        score_single_source = self.calculate_single_source_exposure(
            event.supplier_id, db, gs
        )
        score_buffer_gap = self.calculate_buffer_gap(
            duration_days, earliest_impact_days
        )
        score_regional = self.calculate_regional_risk(event.supplier_id, db)

        # 3. Sum & Normalization (0 to 100)
        raw_total = (
            score_event_sev
            + score_crit
            + score_single_source
            + score_buffer_gap
            + score_regional
        )
        total_risk_score = round(min(100.0, max(0.0, raw_total)), 1)

        # 4. Severity Classification strictly per DESIGN_SYSTEM.md:
        # Low: 0–39, Medium: 40–59, High: 60–79, Critical: 80–100
        severity_label = self.classify_severity(total_risk_score)

        score_breakdown = {
            "event_severity": score_event_sev,
            "criticality": score_crit,
            "single_source_exposure": score_single_source,
            "buffer_gap": score_buffer_gap,
            "regional_risk": score_regional,
            "total": total_risk_score,
        }

        # 5. Deterministic Plain-Language Explanation
        line_names = [l.line_name for l in affected_lines]
        line_str = " and ".join(line_names) if line_names else "assembly operations"

        if earliest_impact_days is not None:
            explanation = (
                f"{supplier.name} is experiencing a {event.event_type} disruption ({duration_days} days). "
                f"With {earliest_impact_days} days of cumulative buffer stock, component supply to {line_str} is at risk."
            )
        else:
            explanation = (
                f"{supplier.name} is experiencing a {event.event_type} disruption ({duration_days} days). "
                f"The disruption is currently fully absorbed by downstream inventory buffers with zero operational downtime."
            )

        return RiskEvaluationResult(
            supplier_id=supplier.id,
            event_id=event.id,
            risk_score=total_risk_score,
            severity_label=severity_label,
            score_breakdown=score_breakdown,
            days_to_impact=earliest_impact_days,
            revenue_at_risk=total_rev_at_risk,
            explanation=explanation,
            affected_nodes=affected_nodes,
            affected_lines=affected_lines,
        )

    def persist_alert(
        self,
        event: DisruptionEvent,
        result: RiskEvaluationResult,
        db: Session,
    ) -> Alert:
        """
        Creates or updates the Alert and AlertAffectedNode database records.
        """
        # Check if an alert already exists for this event
        existing_alert = db.query(Alert).filter(Alert.event_id == event.id).first()

        if existing_alert:
            existing_alert.severity_label = result.severity_label
            existing_alert.risk_score = result.risk_score
            existing_alert.score_breakdown = result.score_breakdown
            existing_alert.days_to_impact = result.days_to_impact
            existing_alert.revenue_at_risk = result.revenue_at_risk
            existing_alert.explanation = result.explanation
            alert_obj = existing_alert
            # Clear existing affected nodes
            db.query(AlertAffectedNode).filter(AlertAffectedNode.alert_id == alert_obj.id).delete()
        else:
            alert_obj = Alert(
                event_id=event.id,
                severity_label=result.severity_label,
                risk_score=result.risk_score,
                score_breakdown=result.score_breakdown,
                days_to_impact=result.days_to_impact,
                revenue_at_risk=result.revenue_at_risk,
                explanation=result.explanation,
                status="open",
            )
            db.add(alert_obj)
            db.flush()

        # Add affected nodes
        for node in result.affected_nodes:
            affected_rec = AlertAffectedNode(
                alert_id=alert_obj.id,
                node_type=node.node_type,
                node_id=node.node_id,
                path_depth=node.path_depth,
                days_to_impact=node.days_to_impact,
            )
            db.add(affected_rec)

        db.commit()
        db.refresh(alert_obj)
        return alert_obj
