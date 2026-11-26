"""
Simulation Engine for TierLens AI (TASK-025).
Provides what-if disruption simulation, mitigation impact evaluation,
and qualified alternative supplier recommendations.
Conforms strictly to project-docs/ARCHITECTURE.md Section 3.8 & 3.9 and API_SPEC.md Section 4.8 & 4.9.
Never mutates the live network graph or confirmed database records.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple, Literal
from datetime import datetime
from sqlalchemy.orm import Session
import networkx as nx

from backend.models.db import (
    Supplier,
    Material,
    Relationship,
    ProductionLine,
    LineRequirement,
    SupplierMaterial,
    Scenario,
    ScenarioResult,
)
from backend.graph.service import GraphService


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class MitigationInput:
    """Input parameters for a mitigation lever."""
    type: Literal["alternate_supplier", "safety_stock", "reroute", "expedite"]
    material_id: Optional[int] = None
    supplier_id: Optional[int] = None
    from_supplier_id: Optional[int] = None
    to_supplier_id: Optional[int] = None
    extra_days: Optional[int] = None
    share_pct: Optional[float] = None
    lead_time_reduction_days: Optional[int] = None


@dataclass
class SimulationLineBreakdown:
    """Detailed downtime and revenue impact for an affected production line."""
    line_id: int
    line_name: str
    daily_revenue: float
    days_to_impact: Optional[int]
    unbuffered_days: int
    revenue_at_risk: float


@dataclass
class SimulationOutcome:
    """Operational impact outcome for a simulation variant (before or after mitigation)."""
    lines_at_risk: int
    revenue_at_risk: float
    days_to_impact: Optional[int]
    affected_path: List[str]
    lines: List[SimulationLineBreakdown] = field(default_factory=list)


@dataclass
class SimulationImprovement:
    """Protection delta achieved by the applied mitigations."""
    revenue_protected: float
    lines_protected: int


@dataclass
class AlternativeRecommendation:
    """Ranked suggestion for an alternative qualified supplier."""
    supplier_id: int
    supplier_name: str
    rank: int
    score: float
    lead_time_days: Optional[int]
    capacity_per_month: Optional[float]
    region_risk: str
    qualified: bool
    existing_relationship: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    """Full simulation result comparing before and after mitigation states."""
    scenario_id: Optional[int]
    name: Optional[str]
    failed_supplier_ids: List[int]
    duration_days: int
    before_mitigation: SimulationOutcome
    after_mitigation: SimulationOutcome
    improvement: SimulationImprovement
    notes: List[str] = field(default_factory=list)


# =============================================================================
# Simulation Engine
# =============================================================================

class SimulationEngine:
    """
    In-memory What-If Disruption Simulator.
    Evaluates hypothetical supplier outages against graph inventory buffers,
    models the impact of mitigation actions, and recommends alternative vendors.
    """

    def __init__(
        self,
        duration_benchmark_days: float = 37.5,
        default_reroute_transition_days: int = 7,
        default_alternate_lead_time_days: int = 14,
    ):
        self.duration_benchmark_days = duration_benchmark_days
        self.default_reroute_transition_days = default_reroute_transition_days
        self.default_alternate_lead_time_days = default_alternate_lead_time_days

    # -------------------------------------------------------------------------
    # Core Simulation Execution
    # -------------------------------------------------------------------------

    def run_simulation(
        self,
        failed_supplier_ids: List[int],
        duration_days: int,
        mitigations: Optional[List[MitigationInput]] = None,
        scenario_name: Optional[str] = None,
        save: bool = False,
        db: Optional[Session] = None,
        graph_service: Optional[GraphService] = None,
    ) -> SimulationResult:
        """
        Executes a hypothetical what-if scenario.
        1. Validates inputs.
        2. Clones the graph and relationship data to guarantee 100% isolation.
        3. Computes the baseline disruption impact ('before_mitigation').
        4. Applies configured mitigation levers to the cloned state.
        5. Computes the mitigated disruption impact ('after_mitigation').
        6. Computes improvement metrics and explanatory notes.
        7. If save=True and a db session is provided, persists to scenarios and scenario_results.
        """
        if not failed_supplier_ids:
            raise ValueError("failed_supplier_ids must contain at least one supplier ID.")
        if duration_days <= 0:
            raise ValueError("duration_days must be a positive integer greater than 0.")
        if db is None:
            raise ValueError("A valid SQLAlchemy database session must be provided.")

        mitigations = mitigations or []

        # Validate that failed suppliers exist
        existing_suppliers = {
            s.id: s for s in db.query(Supplier).filter(Supplier.id.in_(failed_supplier_ids)).all()
        }
        for fid in failed_supplier_ids:
            if fid not in existing_suppliers:
                raise ValueError(f"Supplier with ID {fid} does not exist.")

        # Ensure in-memory graph is initialized, then obtain an isolated copy
        if graph_service is None:
            from backend.graph.service import graph_service as default_gs
            graph_service = default_gs

        if not graph_service.is_built:
            graph_service.rebuild(db)

        # Cloned NetworkX graph ensures zero mutation of the live singleton
        isolated_graph: nx.DiGraph = graph_service.get_graph_copy()
        mfg_id = graph_service.manufacturer_id

        # Preload database records required for simulation
        all_suppliers = {s.id: s for s in db.query(Supplier).all()}
        all_materials = {m.id: m for m in db.query(Material).all()}
        approved_rels = (
            db.query(Relationship)
            .filter(Relationship.status == "approved")
            .all()
        )
        lines_with_reqs = (
            db.query(ProductionLine, LineRequirement.material_id)
            .join(LineRequirement, ProductionLine.id == LineRequirement.line_id)
            .all()
        )

        mat_to_lines: Dict[int, List[ProductionLine]] = {}
        for pline, mat_id in lines_with_reqs:
            mat_to_lines.setdefault(mat_id, []).append(pline)

        # ---------------------------------------------------------------------
        # 1. Baseline Computation (before_mitigation)
        # ---------------------------------------------------------------------
        before_outcome = self._evaluate_propagation(
            failed_supplier_ids=failed_supplier_ids,
            duration_days=duration_days,
            approved_rels=approved_rels,
            mat_to_lines=mat_to_lines,
            mfg_id=mfg_id,
            all_suppliers=all_suppliers,
            isolated_graph=isolated_graph,
            safety_stock_extra_days={},
            alternate_substitutions={},
            expedited_leads={},
        )

        # ---------------------------------------------------------------------
        # 2. Process and Apply Mitigations
        # ---------------------------------------------------------------------
        safety_stock_extra_days: Dict[int, int] = {}
        alternate_substitutions: Dict[int, Dict[str, Any]] = {}
        expedited_leads: Dict[int, int] = {}
        mitigation_notes: List[str] = []

        if len(failed_supplier_ids) > 1:
            failed_names = [
                all_suppliers.get(fid).name if fid in all_suppliers else f"Supplier #{fid}"
                for fid in failed_supplier_ids
            ]
            mitigation_notes.append(
                f"Simulating concurrent multi-supplier disruption across {len(failed_supplier_ids)} suppliers: {', '.join(failed_names)}."
            )

        for mit in mitigations:
            self._apply_mitigation(
                mit=mit,
                db=db,
                failed_supplier_ids=failed_supplier_ids,
                all_suppliers=all_suppliers,
                all_materials=all_materials,
                approved_rels=approved_rels,
                safety_stock_extra_days=safety_stock_extra_days,
                alternate_substitutions=alternate_substitutions,
                expedited_leads=expedited_leads,
                notes=mitigation_notes,
            )

        # ---------------------------------------------------------------------
        # 3. Mitigated Computation (after_mitigation)
        # ---------------------------------------------------------------------
        after_outcome = self._evaluate_propagation(
            failed_supplier_ids=failed_supplier_ids,
            duration_days=duration_days,
            approved_rels=approved_rels,
            mat_to_lines=mat_to_lines,
            mfg_id=mfg_id,
            all_suppliers=all_suppliers,
            isolated_graph=isolated_graph,
            safety_stock_extra_days=safety_stock_extra_days,
            alternate_substitutions=alternate_substitutions,
            expedited_leads=expedited_leads,
        )

        # ---------------------------------------------------------------------
        # 4. Improvement Metrics & Synthesized Explanation Notes
        # ---------------------------------------------------------------------
        revenue_protected = max(0.0, before_outcome.revenue_at_risk - after_outcome.revenue_at_risk)
        lines_protected = max(0, before_outcome.lines_at_risk - after_outcome.lines_at_risk)
        improvement = SimulationImprovement(
            revenue_protected=revenue_protected,
            lines_protected=lines_protected,
        )

        # Build dynamic, high-level summary notes
        final_notes: List[str] = list(mitigation_notes)
        if mitigations:
            if before_outcome.revenue_at_risk > 0 and after_outcome.revenue_at_risk == 0:
                final_notes.append(
                    f"Full disruption protection achieved: ₹{revenue_protected:,.0f} revenue protected across {lines_protected} production lines."
                )
            elif revenue_protected > 0:
                final_notes.append(
                    f"Partial mitigation achieved: revenue at risk reduced by ₹{revenue_protected:,.0f} ({lines_protected} lines protected)."
                )
            else:
                final_notes.append("Applied mitigations were insufficient to reduce line starvation windows.")
        else:
            final_notes.append("Baseline simulation completed with zero active mitigations.")

        # ---------------------------------------------------------------------
        # 5. Optional Persistence (save=True)
        # ---------------------------------------------------------------------
        scenario_id = None
        if save and db is not None:
            scenario_id = self._save_scenario_record(
                name=scenario_name or f"Disruption Simulation ({duration_days} days)",
                failed_supplier_ids=failed_supplier_ids,
                duration_days=duration_days,
                mitigations=mitigations,
                before_outcome=before_outcome,
                after_outcome=after_outcome,
                db=db,
            )

        return SimulationResult(
            scenario_id=scenario_id,
            name=scenario_name,
            failed_supplier_ids=failed_supplier_ids,
            duration_days=duration_days,
            before_mitigation=before_outcome,
            after_mitigation=after_outcome,
            improvement=improvement,
            notes=final_notes,
        )

    # -------------------------------------------------------------------------
    # Downstream BFS Impact Propagation on Cloned State
    # -------------------------------------------------------------------------

    def _evaluate_propagation(
        self,
        failed_supplier_ids: List[int],
        duration_days: int,
        approved_rels: List[Relationship],
        mat_to_lines: Dict[int, List[ProductionLine]],
        mfg_id: Optional[int],
        all_suppliers: Dict[int, Supplier],
        isolated_graph: nx.DiGraph,
        safety_stock_extra_days: Dict[int, int],
        alternate_substitutions: Dict[int, Dict[str, Any]],
        expedited_leads: Dict[int, int],
    ) -> SimulationOutcome:
        """
        Traverses supply relationships downstream from failed suppliers to OEM lines.
        Applies safety stock adjustments, alternate supplier lead-time arrival,
        and capacity constraints in memory.
        """
        # Map relationships by supplier
        supplier_rel_map: Dict[int, List[Relationship]] = {}
        for r in approved_rels:
            supplier_rel_map.setdefault(r.supplier_id, []).append(r)

        # BFS tracking: (supplier_id, depth, cumulative_buffer_days, effective_delay_days, capacity_fraction, origin_failed_id)
        # Queue item: (curr_supp_id, curr_depth, curr_buffer, arrival_delay, cap_coverage, origin_fid)
        visited_buffers: Dict[Tuple[int, int], int] = {}  # (buyer_id, origin_fid) -> min_buffer
        queue: List[Tuple[int, int, int, int, float, int]] = []

        for fid in failed_supplier_ids:
            queue.append((fid, 0, 0, 0, 1.0, fid))
            visited_buffers[(fid, fid)] = 0

        line_impact_map: Dict[int, SimulationLineBreakdown] = {}
        first_disrupted_path: List[str] = []

        while queue:
            curr_supp_id, curr_depth, curr_buffer, arrival_delay, cap_coverage, origin_fid = queue.pop(0)

            outgoing = supplier_rel_map.get(curr_supp_id, [])
            for r in outgoing:
                buyer_id = r.buyer_id
                mat_id = r.material_id

                # Inventory buffer at this hop + any safety stock mitigation applied to this material
                extra_stock = safety_stock_extra_days.get(mat_id, 0)
                hop_buffer = (r.inventory_days or 0) + extra_stock

                # Check if an alternate supplier was engaged for this material
                alt_info = alternate_substitutions.get(mat_id)
                hop_arrival_delay = arrival_delay
                hop_cap_coverage = cap_coverage

                if alt_info is not None:
                    # Alternate supplier lead time (minus any expedited reduction)
                    alt_lead = alt_info["lead_time_days"]
                    hop_arrival_delay = max(hop_arrival_delay, alt_lead)
                    hop_cap_coverage = min(hop_cap_coverage, alt_info["capacity_coverage"])

                # Cumulative buffer up to this hop
                cum_buffer = curr_buffer + hop_buffer
                next_depth = curr_depth + 1

                # If buyer is the OEM Manufacturer -> impact reaches lines consuming this material
                if mfg_id is not None and buyer_id == mfg_id:
                    # Material-specific safety stock application:
                    # - Upstream materials have their safety stock already accumulated in curr_buffer.
                    # - Component materials delivered directly to OEM lines receive their safety stock at this hop.
                    oem_comp_extra_stock = safety_stock_extra_days.get(r.material_id, 0)
                    base_line_buffer = curr_buffer if curr_buffer > 0 else (r.inventory_days or 0)
                    line_buffer = base_line_buffer + oem_comp_extra_stock

                    target_lines = mat_to_lines.get(mat_id, [])
                    for pline in target_lines:
                        daily_rev = float(pline.daily_revenue or 0.0)

                        if hop_arrival_delay > 0:
                            # Starvation window before alternate/rerouted supply arrives
                            lead_time_gap = max(0, min(duration_days, hop_arrival_delay) - line_buffer)
                            # Capacity deficit after arrival
                            post_arrival_days = max(0, duration_days - max(line_buffer, hop_arrival_delay))
                            capacity_deficit_days = (1.0 - hop_cap_coverage) * post_arrival_days
                            unbuf_days = int(round(lead_time_gap + capacity_deficit_days))
                        else:
                            unbuf_days = max(0, duration_days - line_buffer)

                        rev_at_risk = daily_rev * unbuf_days if unbuf_days > 0 else 0.0

                        prev_line = line_impact_map.get(pline.id)
                        if prev_line:
                            effective_buffer = (
                                min(prev_line.days_to_impact, line_buffer)
                                if prev_line.days_to_impact is not None
                                else line_buffer
                            )
                            effective_unbuf = max(prev_line.unbuffered_days, unbuf_days)
                            effective_rev = daily_rev * effective_unbuf if effective_unbuf > 0 else 0.0
                            line_impact_map[pline.id] = SimulationLineBreakdown(
                                line_id=pline.id,
                                line_name=pline.name,
                                daily_revenue=daily_rev,
                                days_to_impact=effective_buffer,
                                unbuffered_days=effective_unbuf,
                                revenue_at_risk=effective_rev,
                            )
                        else:
                            line_impact_map[pline.id] = SimulationLineBreakdown(
                                line_id=pline.id,
                                line_name=pline.name,
                                daily_revenue=daily_rev,
                                days_to_impact=line_buffer,
                                unbuffered_days=unbuf_days,
                                revenue_at_risk=rev_at_risk,
                            )

                        # Trace primary affected path for reporting (from origin failed supplier to line)
                        if not first_disrupted_path and unbuf_days > 0:
                            from backend.graph.service import to_node_id, parse_supplier_id
                            try:
                                u = to_node_id(origin_fid)
                                v = to_node_id(curr_supp_id)
                                if u == v:
                                    path_names = [all_suppliers.get(origin_fid).name if all_suppliers.get(origin_fid) else f"Supplier #{origin_fid}"]
                                else:
                                    path_nodes = nx.shortest_path(isolated_graph, u, v)
                                    path_names = [all_suppliers.get(parse_supplier_id(n)).name if all_suppliers.get(parse_supplier_id(n)) else f"Supplier #{n}" for n in path_nodes]
                                path_names.append(pline.name)
                                first_disrupted_path = path_names
                            except Exception:
                                origin_name = all_suppliers.get(origin_fid).name if all_suppliers.get(origin_fid) else f"Supplier #{origin_fid}"
                                first_disrupted_path = [origin_name, pline.name]
                else:
                    # Intermediate downstream supplier hop
                    visited_key = (buyer_id, origin_fid)
                    if visited_key not in visited_buffers or cum_buffer < visited_buffers[visited_key]:
                        visited_buffers[visited_key] = cum_buffer
                        queue.append((buyer_id, next_depth, cum_buffer, hop_arrival_delay, hop_cap_coverage, origin_fid))

        lines_list = sorted(line_impact_map.values(), key=lambda l: l.line_id)
        lines_at_risk_count = sum(1 for l in lines_list if l.unbuffered_days > 0)
        total_rev_at_risk = sum(l.revenue_at_risk for l in lines_list)

        earliest_impact: Optional[int] = None
        if lines_at_risk_count > 0:
            impacted_line_buffers = [l.days_to_impact for l in lines_list if l.unbuffered_days > 0 and l.days_to_impact is not None]
            earliest_impact = min(impacted_line_buffers, default=None)
        else:
            total_rev_at_risk = 0.0
            first_disrupted_path = []

        return SimulationOutcome(
            lines_at_risk=lines_at_risk_count,
            revenue_at_risk=total_rev_at_risk,
            days_to_impact=earliest_impact,
            affected_path=first_disrupted_path,
            lines=lines_list,
        )

    # -------------------------------------------------------------------------
    # Mitigation Applicators
    # -------------------------------------------------------------------------

    def _apply_mitigation(
        self,
        mit: MitigationInput,
        db: Session,
        failed_supplier_ids: List[int],
        all_suppliers: Dict[int, Supplier],
        all_materials: Dict[int, Material],
        approved_rels: List[Relationship],
        safety_stock_extra_days: Dict[int, int],
        alternate_substitutions: Dict[int, Dict[str, Any]],
        expedited_leads: Dict[int, int],
        notes: List[str],
    ) -> None:
        """Validates and stages a mitigation lever into memory."""
        # 1. Safety Stock
        if mit.type == "safety_stock":
            if mit.material_id is None:
                raise ValueError("safety_stock mitigation requires 'material_id'.")
            if mit.extra_days is None or mit.extra_days <= 0:
                raise ValueError("safety_stock mitigation requires positive 'extra_days'.")

            mat_name = all_materials.get(mit.material_id).name if mit.material_id in all_materials else f"Material #{mit.material_id}"
            safety_stock_extra_days[mit.material_id] = safety_stock_extra_days.get(mit.material_id, 0) + mit.extra_days
            notes.append(f"Added {mit.extra_days} days safety stock buffer for {mat_name}.")

        # 2. Expedite
        elif mit.type == "expedite":
            if mit.supplier_id is None:
                raise ValueError("expedite mitigation requires 'supplier_id'.")
            if mit.lead_time_reduction_days is None or mit.lead_time_reduction_days <= 0:
                raise ValueError("expedite mitigation requires positive 'lead_time_reduction_days'.")

            supp_name = all_suppliers.get(mit.supplier_id).name if mit.supplier_id in all_suppliers else f"Supplier #{mit.supplier_id}"
            expedited_leads[mit.supplier_id] = mit.lead_time_reduction_days
            notes.append(f"Expedited logistics for {supp_name}: lead time reduced by {mit.lead_time_reduction_days} days.")

        # 3. Alternate Supplier
        elif mit.type == "alternate_supplier":
            if mit.material_id is None:
                raise ValueError("alternate_supplier mitigation requires 'material_id'.")
            if mit.supplier_id is None:
                raise ValueError("alternate_supplier mitigation requires 'supplier_id'.")
            if mit.supplier_id in failed_supplier_ids:
                raise ValueError(f"Supplier #{mit.supplier_id} is disrupted and cannot serve as an alternate.")

            alt_supplier = all_suppliers.get(mit.supplier_id)
            if not alt_supplier:
                raise ValueError(f"Alternate supplier #{mit.supplier_id} does not exist.")

            mat_name = all_materials.get(mit.material_id).name if mit.material_id in all_materials else f"Material #{mit.material_id}"

            # Check supplier qualification and capability in SupplierMaterial table
            sup_mat = (
                db.query(SupplierMaterial)
                .filter(
                    SupplierMaterial.supplier_id == mit.supplier_id,
                    SupplierMaterial.material_id == mit.material_id,
                )
                .first()
            )

            # Determine baseline lead time from DB capability, relationship, or configurable default
            if sup_mat and sup_mat.typical_lead_time_days:
                base_lead = sup_mat.typical_lead_time_days
                lead_source = f"supplier catalog ({base_lead} days)"
            else:
                rel = next((r for r in approved_rels if r.supplier_id == mit.supplier_id and r.material_id == mit.material_id and r.lead_time_days), None)
                if rel and rel.lead_time_days:
                    base_lead = rel.lead_time_days
                    lead_source = f"approved relationship ({base_lead} days)"
                else:
                    base_lead = self.default_alternate_lead_time_days
                    lead_source = f"default configurable assumption ({base_lead} days)"
                    notes.append(
                        f"Note: Alternate supplier {alt_supplier.name} has no recorded lead time for {mat_name}; "
                        f"using {lead_source}."
                    )

            # Apply any expedite reduction
            expedite_reduction = expedited_leads.get(mit.supplier_id, 0)
            effective_lead = max(1, base_lead - expedite_reduction)

            # Demand evaluation: resolve from contracted volume or nominal capacity of failed suppliers
            contracted_demand = sum(
                (r.quantity_per_month or 0.0)
                for r in approved_rels
                if r.supplier_id in failed_supplier_ids and r.material_id == mit.material_id
            )
            if contracted_demand > 0:
                req_volume = contracted_demand
                demand_source = f"contracted volume ({req_volume:,.1f} units/month)"
            else:
                failed_caps = [
                    sm.capacity_per_month
                    for sm in db.query(SupplierMaterial).filter(
                        SupplierMaterial.supplier_id.in_(failed_supplier_ids),
                        SupplierMaterial.material_id == mit.material_id,
                    ).all()
                    if sm.capacity_per_month
                ]
                if failed_caps:
                    req_volume = sum(failed_caps)
                    demand_source = f"nominal supplier capacity ({req_volume:,.1f} units/month)"
                else:
                    req_volume = 0.0
                    demand_source = "unrecorded demand"
                    notes.append(
                        f"Note: Monthly demand for {mat_name} is unrecorded across failed suppliers; "
                        "assuming full capacity coverage."
                    )

            # Capacity evaluation
            avail_capacity = sup_mat.capacity_per_month if (sup_mat and sup_mat.capacity_per_month) else (alt_supplier.capacity_per_month or req_volume)

            # Share percentage evaluation
            share_factor = 1.0
            if mit.share_pct is not None:
                if mit.share_pct <= 0 or mit.share_pct > 100:
                    raise ValueError("share_pct must be between 0 and 100.")
                share_factor = mit.share_pct / 100.0

            if req_volume > 0:
                capacity_coverage = min(avail_capacity / req_volume, share_factor)
            else:
                capacity_coverage = share_factor

            capacity_coverage = max(0.0, min(1.0, capacity_coverage))

            alternate_substitutions[mit.material_id] = {
                "supplier_id": mit.supplier_id,
                "lead_time_days": effective_lead,
                "capacity_coverage": capacity_coverage,
            }

            qualification_status = "qualified" if (sup_mat and sup_mat.is_qualified) else "unqualified"
            note_msg = (
                f"Engaged alternate supplier {alt_supplier.name} for {mat_name}: "
                f"lead time {effective_lead} days ({lead_source}), "
                f"capacity coverage {capacity_coverage * 100:.0f}% based on {demand_source} ({qualification_status})."
            )
            notes.append(note_msg)

        # 4. Reroute
        elif mit.type == "reroute":
            if mit.from_supplier_id is None or mit.to_supplier_id is None or mit.material_id is None:
                raise ValueError("reroute mitigation requires 'from_supplier_id', 'to_supplier_id', and 'material_id'.")

            from_name = all_suppliers.get(mit.from_supplier_id).name if mit.from_supplier_id in all_suppliers else f"Supplier #{mit.from_supplier_id}"
            to_name = all_suppliers.get(mit.to_supplier_id).name if mit.to_supplier_id in all_suppliers else f"Supplier #{mit.to_supplier_id}"
            mat_name = all_materials.get(mit.material_id).name if mit.material_id in all_materials else f"Material #{mit.material_id}"

            # Resolve transition lead time from DB relationship, catalog, or configurable fallback
            direct_rel = next(
                (r for r in approved_rels if r.supplier_id == mit.from_supplier_id and r.buyer_id == mit.to_supplier_id and r.material_id == mit.material_id and r.lead_time_days),
                None,
            )
            if direct_rel and direct_rel.lead_time_days:
                transition_lead = direct_rel.lead_time_days
                lead_source = f"confirmed relationship ({transition_lead} days)"
            else:
                from_sm = (
                    db.query(SupplierMaterial)
                    .filter(
                        SupplierMaterial.supplier_id == mit.from_supplier_id,
                        SupplierMaterial.material_id == mit.material_id,
                    )
                    .first()
                )
                if from_sm and from_sm.typical_lead_time_days:
                    transition_lead = from_sm.typical_lead_time_days
                    lead_source = f"supplier catalog ({transition_lead} days)"
                else:
                    transition_lead = self.default_reroute_transition_days
                    lead_source = f"default configurable assumption ({transition_lead} days)"
                    notes.append(
                        f"Note: Reroute path from {from_name} to {to_name} for {mat_name} has no recorded lead time; "
                        f"using {lead_source}."
                    )

            # Apply any expedite reduction
            expedite_reduction = expedited_leads.get(mit.from_supplier_id, 0)
            effective_transition = max(1, transition_lead - expedite_reduction)

            # Treat rerouting as an active alternate supply route with determined transfer lead time
            alternate_substitutions[mit.material_id] = {
                "supplier_id": mit.from_supplier_id,
                "lead_time_days": effective_transition,
                "capacity_coverage": 1.0,
            }
            notes.append(
                f"Rerouted {mat_name} flow from {from_name} to {to_name}: "
                f"transition lead time {effective_transition} days ({lead_source})."
            )

        else:
            raise ValueError(f"Unsupported mitigation type: {mit.type}")

    # -------------------------------------------------------------------------
    # Alternative Supplier Recommender
    # -------------------------------------------------------------------------

    def recommend_alternatives(
        self,
        supplier_id: int,
        material_id: Optional[int] = None,
        limit: int = 5,
        db: Optional[Session] = None,
    ) -> List[AlternativeRecommendation]:
        """
        Recommends alternative suppliers for materials provided by supplier_id.
        Ranks by weighted multi-criteria score (qualification, lead time, capacity, regional risk).
        """
        if db is None:
            raise ValueError("A valid SQLAlchemy database session must be provided.")

        target_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not target_supplier:
            raise ValueError(f"Supplier with ID {supplier_id} does not exist.")

        # Identify materials supplied by target supplier
        if material_id is not None:
            target_materials = [material_id]
        else:
            sup_mats = db.query(SupplierMaterial.material_id).filter(SupplierMaterial.supplier_id == supplier_id).all()
            rel_mats = db.query(Relationship.material_id).filter(Relationship.supplier_id == supplier_id).all()
            target_materials = list({m[0] for m in sup_mats} | {r[0] for r in rel_mats})

        if not target_materials:
            return []

        # Target supplier's baseline parameters for comparison
        target_sup_mat = (
            db.query(SupplierMaterial)
            .filter(SupplierMaterial.supplier_id == supplier_id, SupplierMaterial.material_id.in_(target_materials))
            .first()
        )
        target_lead = target_sup_mat.typical_lead_time_days if (target_sup_mat and target_sup_mat.typical_lead_time_days) else 21

        # Query potential candidate suppliers providing these materials
        candidate_sup_mats = (
            db.query(SupplierMaterial, Supplier)
            .join(Supplier, SupplierMaterial.supplier_id == Supplier.id)
            .filter(
                SupplierMaterial.material_id.in_(target_materials),
                SupplierMaterial.supplier_id != supplier_id,
                Supplier.is_active == True,
            )
            .all()
        )

        # Check existing relationships
        existing_rel_supp_ids = {
            r[0]
            for r in db.query(Relationship.supplier_id)
            .filter(Relationship.status == "approved")
            .all()
        }

        recommendations: List[AlternativeRecommendation] = []

        for sm, supp in candidate_sup_mats:
            mat_obj = db.query(Material).filter(Material.id == sm.material_id).first()
            mat_name = mat_obj.name if mat_obj else f"Material #{sm.material_id}"

            lead_days = sm.typical_lead_time_days or 14
            cap = sm.capacity_per_month or supp.capacity_per_month
            region = supp.region or "Unknown"
            country = supp.country or "Unknown"

            # Regional risk factor (India / South Asia / Domestic = low, other = medium)
            reg_risk = "low" if (supp.country == "India" or supp.region == "South Asia") else "medium"
            has_existing = supp.id in existing_rel_supp_ids

            # Multi-factor scoring (0.0 to 1.0)
            # 1. Qualification (weight: 0.35)
            qual_score = 0.35 if sm.is_qualified else 0.0

            # 2. Lead time advantage (weight: 0.25)
            # Shorter than current supplier gets full weight; longer scales down
            lead_ratio = min(1.0, max(0.2, target_lead / max(1, lead_days)))
            lead_score = 0.25 * lead_ratio

            # 3. Capacity availability (weight: 0.20)
            cap_score = 0.20 if (cap and cap >= 80) else 0.10

            # 4. Regional risk (weight: 0.10)
            reg_score = 0.10 if reg_risk == "low" else 0.05

            # 5. Existing relationship familiarity (weight: 0.10)
            rel_score = 0.10 if has_existing else 0.04

            total_score = round(qual_score + lead_score + cap_score + reg_score + rel_score, 2)

            # Build human-readable reasons
            reasons: List[str] = []
            if sm.is_qualified:
                reasons.append(f"Qualified for {mat_name}")
            else:
                reasons.append(f"Provides {mat_name} (qualification pending)")

            if lead_days < target_lead:
                reasons.append(f"Shorter lead time than current supplier ({lead_days} days vs {target_lead} days)")
            else:
                reasons.append(f"Lead time: {lead_days} days")

            if reg_risk == "low":
                reasons.append(f"Located in lower-risk region ({country} / {region})")

            if cap:
                reasons.append(f"Monthly capacity: {cap:,.0f} units")

            if has_existing:
                reasons.append("Pre-existing relationship in enterprise network")

            recommendations.append(
                AlternativeRecommendation(
                    supplier_id=supp.id,
                    supplier_name=supp.name,
                    rank=0,  # Assigned after sorting
                    score=total_score,
                    lead_time_days=lead_days,
                    capacity_per_month=cap,
                    region_risk=reg_risk,
                    qualified=bool(sm.is_qualified),
                    existing_relationship=has_existing,
                    reasons=reasons,
                )
            )

        # Deterministic sorting: highest score first, then shortest lead time, then lower supplier ID
        recommendations.sort(key=lambda r: (-r.score, r.lead_time_days or 999, r.supplier_id))
        actual_limit = int(limit) if isinstance(limit, (int, float)) else 5
        top_recommendations = recommendations[:actual_limit]
        for idx, rec in enumerate(top_recommendations, start=1):
            rec.rank = idx

        return top_recommendations

    # -------------------------------------------------------------------------
    # Scenario Persistence
    # -------------------------------------------------------------------------

    def _save_scenario_record(
        self,
        name: str,
        failed_supplier_ids: List[int],
        duration_days: int,
        mitigations: List[MitigationInput],
        before_outcome: SimulationOutcome,
        after_outcome: SimulationOutcome,
        db: Session,
    ) -> int:
        """Saves scenario inputs and both result variants to database."""
        mit_dicts = [
            {
                "type": m.type,
                "material_id": m.material_id,
                "supplier_id": m.supplier_id,
                "from_supplier_id": m.from_supplier_id,
                "to_supplier_id": m.to_supplier_id,
                "extra_days": m.extra_days,
                "share_pct": m.share_pct,
                "lead_time_reduction_days": m.lead_time_reduction_days,
            }
            for m in mitigations
        ]

        scenario = Scenario(
            name=name,
            failed_supplier_ids=failed_supplier_ids,
            duration_days=duration_days,
            mitigations=mit_dicts,
        )
        db.add(scenario)
        db.flush()

        # Before mitigation result variant
        res_before = ScenarioResult(
            scenario_id=scenario.id,
            variant="before_mitigation",
            lines_at_risk=before_outcome.lines_at_risk,
            revenue_at_risk=before_outcome.revenue_at_risk,
            days_to_impact=before_outcome.days_to_impact,
            affected_path=before_outcome.affected_path,
            result_detail={
                "lines": [
                    {
                        "line_id": l.line_id,
                        "line_name": l.line_name,
                        "daily_revenue": l.daily_revenue,
                        "days_to_impact": l.days_to_impact,
                        "unbuffered_days": l.unbuffered_days,
                        "revenue_at_risk": l.revenue_at_risk,
                    }
                    for l in before_outcome.lines
                ]
            },
        )
        db.add(res_before)

        # After mitigation result variant
        res_after = ScenarioResult(
            scenario_id=scenario.id,
            variant="after_mitigation",
            lines_at_risk=after_outcome.lines_at_risk,
            revenue_at_risk=after_outcome.revenue_at_risk,
            days_to_impact=after_outcome.days_to_impact,
            affected_path=after_outcome.affected_path,
            result_detail={
                "lines": [
                    {
                        "line_id": l.line_id,
                        "line_name": l.line_name,
                        "daily_revenue": l.daily_revenue,
                        "days_to_impact": l.days_to_impact,
                        "unbuffered_days": l.unbuffered_days,
                        "revenue_at_risk": l.revenue_at_risk,
                    }
                    for l in after_outcome.lines
                ]
            },
        )
        db.add(res_after)
        db.commit()

        return scenario.id
