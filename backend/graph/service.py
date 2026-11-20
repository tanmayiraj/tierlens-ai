"""
Graph service module using NetworkX for multi-tier supplier network modeling.
Conforms to project-docs/ARCHITECTURE.md Section 3.4, project-docs/AGENTS.md Section 6,
and project-docs/TASKS.md (TASK-008 and TASK-009).
"""

from typing import Optional, List, Dict, Set, Any, Union
import threading
import itertools
from datetime import datetime, timezone
import networkx as nx
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.db import (
    Supplier,
    Relationship,
    RelationshipEvidence,
)


class GraphServiceError(Exception):
    """Base exception for GraphService errors."""
    pass


class ManufacturerNotFoundError(GraphServiceError):
    """Raised when no active manufacturer is found in the database."""
    pass


class MultipleManufacturersError(GraphServiceError):
    """Raised when multiple active manufacturers exist and none was explicitly specified."""
    pass


def to_node_id(supplier_id: int) -> str:
    """Formats an integer supplier ID into the standard graph node ID string: 'supplier:{id}'."""
    return f"supplier:{supplier_id}"


def parse_supplier_id(node_ref: Union[str, int]) -> int:
    """Parses an integer supplier ID from either an int or a node string like 'supplier:7'."""
    if isinstance(node_ref, int):
        return node_ref
    if isinstance(node_ref, str):
        if node_ref.startswith("supplier:"):
            return int(node_ref.split(":", 1)[1])
        return int(node_ref)
    raise ValueError(f"Cannot parse supplier ID from {type(node_ref)}: {node_ref}")


class GraphService:
    """
    Manages an in-memory directed supplier network (nx.DiGraph) representing material flows
    from upstream suppliers to downstream buyers.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._lock = threading.RLock()
        self._manufacturer_id: Optional[int] = None
        self._max_tier: int = 0
        self._built_at: Optional[datetime] = None
        self._has_cycles: bool = False
        self._cycles: List[List[int]] = []

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def is_built(self) -> bool:
        """Returns True if the in-memory graph has been built at least once."""
        with self._lock:
            return self._built_at is not None

    @property
    def manufacturer_id(self) -> Optional[int]:
        """Returns the ID of the manufacturer relative to which tiers are computed."""
        with self._lock:
            return self._manufacturer_id

    @property
    def max_tier(self) -> int:
        """Returns the maximum computed supplier tier in the graph."""
        with self._lock:
            return self._max_tier

    @property
    def built_at(self) -> Optional[datetime]:
        """Returns the UTC datetime when the graph was last rebuilt."""
        with self._lock:
            return self._built_at

    @property
    def has_cycles(self) -> bool:
        """Returns True if directed cycles were detected during graph construction."""
        with self._lock:
            return self._has_cycles

    @property
    def node_count(self) -> int:
        """Returns the number of nodes in the active graph."""
        with self._lock:
            return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Returns the number of edges in the active graph."""
        with self._lock:
            return self._graph.number_of_edges()

    def get_graph_copy(self) -> nx.DiGraph:
        """Returns a copy of the active in-memory directed graph."""
        with self._lock:
            return self._graph.copy()

    # -------------------------------------------------------------------------
    # Manufacturer Resolution
    # -------------------------------------------------------------------------

    def resolve_manufacturer_id(self, db: Session, manufacturer_id: Optional[int] = None) -> int:
        """
        Identifies the manufacturer supplier record.
        - If manufacturer_id is supplied, verifies it exists, is active, and entity_type == 'manufacturer'.
        - If manufacturer_id is None, queries active manufacturers. Raises if 0 or > 1.
        """
        if manufacturer_id is not None:
            mfg = (
                db.query(Supplier)
                .filter(
                    Supplier.id == manufacturer_id,
                    Supplier.is_active == True,
                    Supplier.entity_type == "manufacturer",
                )
                .first()
            )
            if not mfg:
                raise ManufacturerNotFoundError(
                    f"Manufacturer with id {manufacturer_id} was not found, is inactive, or is not entity_type 'manufacturer'."
                )
            return mfg.id

        manufacturers = (
            db.query(Supplier)
            .filter(
                Supplier.is_active == True,
                Supplier.entity_type == "manufacturer",
            )
            .all()
        )

        if len(manufacturers) == 0:
            raise ManufacturerNotFoundError("No active manufacturer found in the database.")
        if len(manufacturers) > 1:
            mfg_ids = [m.id for m in manufacturers]
            raise MultipleManufacturersError(
                f"Multiple active manufacturers found ({mfg_ids}). Please specify manufacturer_id explicitly."
            )

        return manufacturers[0].id

    # -------------------------------------------------------------------------
    # Graph Construction & Tier Synchronization
    # -------------------------------------------------------------------------

    def rebuild(self, db: Session, manufacturer_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Rebuilds the in-memory directed graph from approved relationships and active suppliers.
        Computes tiers relative to the resolved manufacturer, synchronizes tiers to relationships.tier,
        and atomically swaps the active graph.
        """
        # 1. Resolve manufacturer explicitly
        mfg_id = self.resolve_manufacturer_id(db, manufacturer_id)

        # 2. Build temporary graph
        temp_graph = nx.DiGraph()

        # 3. Load active suppliers only
        active_suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
        active_supplier_ids = {s.id for s in active_suppliers}

        for s in active_suppliers:
            temp_graph.add_node(
                to_node_id(s.id),
                id=s.id,
                name=s.name,
                entity_type=s.entity_type,
                country=s.country,
                region=s.region,
                latitude=s.latitude,
                longitude=s.longitude,
                capacity_per_month=s.capacity_per_month,
                base_risk=s.base_risk,
                tier=None,
            )

        # 4. Load approved relationships between active suppliers only
        approved_rels = (
            db.query(Relationship)
            .filter(
                Relationship.status == "approved",
                Relationship.supplier_id.in_(active_supplier_ids),
                Relationship.buyer_id.in_(active_supplier_ids),
            )
            .all()
        )

        # Calculate evidence counts using junction table with fallback
        rel_ids = [r.id for r in approved_rels]
        evidence_counts: Dict[int, int] = {}
        if rel_ids:
            counts = (
                db.query(
                    RelationshipEvidence.relationship_id,
                    func.count(RelationshipEvidence.evidence_id),
                )
                .filter(RelationshipEvidence.relationship_id.in_(rel_ids))
                .group_by(RelationshipEvidence.relationship_id)
                .all()
            )
            for rid, c in counts:
                evidence_counts[rid] = c

        # Add directed edges: supplier (upstream) -> buyer (downstream)
        for r in approved_rels:
            ev_count = evidence_counts.get(r.id, 0)
            if ev_count == 0 and r.evidence_id is not None:
                ev_count = 1

            u = to_node_id(r.supplier_id)
            v = to_node_id(r.buyer_id)

            temp_graph.add_edge(
                u,
                v,
                relationship_id=r.id,
                material_id=r.material_id,
                material=r.material.name if r.material else "",
                lead_time_days=r.lead_time_days,
                share_pct=r.share_pct,
                inventory_days=r.inventory_days,
                quantity_per_month=r.quantity_per_month,
                confidence=r.confidence,
                status=r.status,
                evidence_id=r.evidence_id,
                evidence_count=ev_count,
            )

        # 5. Calculate tiers using the reversed graph and shortest-path lengths
        # In temp_graph: S -> B (e.g. Tier 1 -> Manufacturer).
        # In reversed graph: Manufacturer -> Tier 1 -> Tier 2 -> Tier 3.
        mfg_node = to_node_id(mfg_id)
        G_rev = temp_graph.reverse()

        supplier_tiers: Dict[int, Optional[int]] = {s_id: None for s_id in active_supplier_ids}
        if mfg_node in G_rev:
            lengths = nx.single_source_shortest_path_length(G_rev, source=mfg_node)
            for node_id, dist in lengths.items():
                s_id = parse_supplier_id(node_id)
                supplier_tiers[s_id] = dist
                if node_id in temp_graph.nodes:
                    temp_graph.nodes[node_id]["tier"] = dist

        # 6. Synchronize computed tiers to relationships in database
        # - Eligible approved relationships get their tier set to the upstream supplier's tier.
        # - Stale or ineligible relationships get their tier cleared to None (NULL).
        all_relationships = db.query(Relationship).all()
        for r in all_relationships:
            s_tier = supplier_tiers.get(r.supplier_id)
            if (
                r.status == "approved"
                and r.supplier_id in active_supplier_ids
                and r.buyer_id in active_supplier_ids
                and s_tier is not None
                and s_tier >= 1
            ):
                target_tier = s_tier
            else:
                target_tier = None

            if r.tier != target_tier:
                r.tier = target_tier

        # Execute safe transaction
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        # 7. Cycle detection (bounded to avoid exponential blowup)
        is_dag = nx.is_directed_acyclic_graph(temp_graph)
        has_cycles = not is_dag
        cycle_list: List[List[int]] = []
        if has_cycles:
            cycle_gen = nx.simple_cycles(temp_graph)
            for cyc in itertools.islice(cycle_gen, 100):
                cycle_list.append([parse_supplier_id(n) for n in cyc])

        # 8. Atomically swap in-memory graph
        with self._lock:
            self._graph = temp_graph
            self._manufacturer_id = mfg_id
            self._max_tier = max((t for t in supplier_tiers.values() if t is not None), default=0)
            self._built_at = datetime.now(timezone.utc)
            self._has_cycles = has_cycles
            self._cycles = cycle_list

        return {
            "nodes": temp_graph.number_of_nodes(),
            "edges": temp_graph.number_of_edges(),
            "max_tier": self._max_tier,
            "built_at": self._built_at.isoformat(),
            "manufacturer_id": mfg_id,
            "has_cycles": has_cycles,
        }

    # -------------------------------------------------------------------------
    # Traversal Methods
    # -------------------------------------------------------------------------

    def get_direct_suppliers(self, supplier_id: Union[int, str]) -> List[int]:
        """Returns direct upstream suppliers feeding the given supplier."""
        node_id = to_node_id(parse_supplier_id(supplier_id))
        with self._lock:
            if node_id not in self._graph:
                return []
            return sorted([parse_supplier_id(p) for p in self._graph.predecessors(node_id)])

    def get_direct_buyers(self, supplier_id: Union[int, str]) -> List[int]:
        """Returns direct downstream buyers that the given supplier feeds."""
        node_id = to_node_id(parse_supplier_id(supplier_id))
        with self._lock:
            if node_id not in self._graph:
                return []
            return sorted([parse_supplier_id(s) for s in self._graph.successors(node_id)])

    def get_upstream_ancestors(self, supplier_id: Union[int, str]) -> Set[int]:
        """Returns all upstream supplier IDs across all tiers feeding the given supplier."""
        node_id = to_node_id(parse_supplier_id(supplier_id))
        with self._lock:
            if node_id not in self._graph:
                return set()
            return {parse_supplier_id(a) for a in nx.ancestors(self._graph, node_id)}

    def get_downstream_descendants(self, supplier_id: Union[int, str]) -> Set[int]:
        """Returns all downstream entity IDs across all tiers affected by the given supplier."""
        node_id = to_node_id(parse_supplier_id(supplier_id))
        with self._lock:
            if node_id not in self._graph:
                return set()
            return {parse_supplier_id(d) for d in nx.descendants(self._graph, node_id)}

    def has_path(self, source_supplier_id: Union[int, str], target_supplier_id: Union[int, str]) -> bool:
        """Returns True if a directed path exists from source_supplier to target_supplier."""
        u = to_node_id(parse_supplier_id(source_supplier_id))
        v = to_node_id(parse_supplier_id(target_supplier_id))
        with self._lock:
            if u not in self._graph or v not in self._graph:
                return False
            return nx.has_path(self._graph, u, v)

    def shortest_path(
        self, source_supplier_id: Union[int, str], target_supplier_id: Union[int, str]
    ) -> Optional[List[int]]:
        """Returns the shortest path of supplier IDs from source to target, or None if unreachable."""
        u = to_node_id(parse_supplier_id(source_supplier_id))
        v = to_node_id(parse_supplier_id(target_supplier_id))
        with self._lock:
            if u not in self._graph or v not in self._graph:
                return None
            try:
                path = nx.shortest_path(self._graph, source=u, target=v)
                return [parse_supplier_id(n) for n in path]
            except nx.NetworkXNoPath:
                return None

    def get_node_data(self, supplier_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Returns attributes for a given supplier node, or None if not present."""
        node_id = to_node_id(parse_supplier_id(supplier_id))
        with self._lock:
            if node_id not in self._graph:
                return None
            return dict(self._graph.nodes[node_id])

    def get_edge_data(
        self, supplier_id: Union[int, str], buyer_id: Union[int, str]
    ) -> Optional[Dict[str, Any]]:
        """Returns attributes for the directed edge between supplier and buyer, or None if absent."""
        u = to_node_id(parse_supplier_id(supplier_id))
        v = to_node_id(parse_supplier_id(buyer_id))
        with self._lock:
            if not self._graph.has_edge(u, v):
                return None
            return dict(self._graph.edges[u, v])

    def detect_cycles(self, max_cycles: int = 100) -> List[List[int]]:
        """
        Returns detected directed cycles in the graph up to max_cycles.
        Does not delete or modify any graph elements.
        """
        with self._lock:
            if not self._graph or nx.is_directed_acyclic_graph(self._graph):
                return []
            cycle_gen = nx.simple_cycles(self._graph)
            cycles: List[List[int]] = []
            for cyc in itertools.islice(cycle_gen, max_cycles):
                cycles.append([parse_supplier_id(n) for n in cyc])
            return cycles


# Global service instance for dependency injection
graph_service = GraphService()
