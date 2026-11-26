"""
Supplier and Material Entity Resolution Service for TierLens AI (Milestone 4: TASK-023 / Step 4.2).
Resolves extracted entity mentions to canonical supplier and material records in SQLite using a
multi-stage matching pipeline:
  1. Exact canonical name match
  2. Exact alias match
  3. Legal suffix normalization match
  4. RapidFuzz token_sort_ratio fuzzy match (>= 90% threshold)
  5. Ambiguity detection and rejection

Conforms to ARCHITECTURE.md Section 3.3 and DATABASE_SCHEMA.md Section 3.2, 3.3, 3.4.
All operations respect the caller's transaction boundaries and use flush() without commit().
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Set, Tuple, Literal

from rapidfuzz import fuzz
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.db import Supplier, SupplierAlias, Material

logger = logging.getLogger(__name__)

# Standard statutory corporate legal suffixes removed during company name normalization.
# Business descriptors (e.g. 'industries', 'components', 'enterprises') are deliberately
# excluded to prevent distinct corporate entities from being falsely merged.
LEGAL_COMPANY_TOKENS: Set[str] = {
    "pvt",
    "ltd",
    "inc",
    "llc",
    "corp",
    "corporation",
    "co",
    "company",
    "holdings",
    "holding",
    "gmbh",
    "ag",
    "sa",
    "plc",
    "private",
    "limited",
    "incorporated",
}


def normalize_company_name(name: str) -> str:
    """
    Normalizes a company/supplier name by lowercasing, stripping punctuation,
    and removing standard corporate legal suffixes (e.g. 'Pvt Ltd', 'Inc', 'Industries').
    Preserves root brand tokens and protects short names from over-stripping.

    Examples:
      'GreenLatex Pvt Ltd' -> 'greenlatex'
      'RubberCore Industries' -> 'rubbercore'
      'AutoMotive Corp.' -> 'automotive'
      'ABC Rubber Pvt Ltd' -> 'abc rubber'
      '3M' -> '3m'
    """
    if not name or not name.strip():
        return ""

    text = name.strip().lower()
    # Replace ampersands with 'and'
    text = re.sub(r"&", " and ", text)
    # Strip common punctuation (periods, commas, hyphens, brackets, quotes)
    text = re.sub(r"[,\.()\[\]\"'–—\-_/\\:]", " ", text)
    tokens = text.split()

    filtered = [t for t in tokens if t not in LEGAL_COMPANY_TOKENS]
    # Strip trailing or leading connecting words left behind after suffix stripping
    while len(filtered) > 1 and filtered[-1] in {"and", "the"}:
        filtered.pop()
    while len(filtered) > 1 and filtered[0] in {"the"}:
        filtered.pop(0)

    # If filtering removed every single token, retain the cleaned original tokens
    if not filtered:
        filtered = tokens

    return " ".join(filtered).strip()


def normalize_material_name(name: str) -> str:
    """
    Normalizes a material name by lowercasing, stripping punctuation,
    and collapsing whitespace.

    Examples:
      'Natural Latex' -> 'natural latex'
      'Rubber Seals - Grade A' -> 'rubber seals grade a'
    """
    if not name or not name.strip():
        return ""

    text = name.strip().lower()
    text = re.sub(r"[,\.()\[\]\"'–—\-_/\\:]", " ", text)
    tokens = text.split()
    return " ".join(tokens).strip()


def infer_material_type(name: str) -> Literal["raw", "part", "assembly"]:
    """
    Infers the material_type based on material name keywords:
      - 'assembly' for assemblies, modules, systems
      - 'part' for components, seals, gaskets, wires, sensors, valves, parts
      - 'raw' as the default for raw materials (rubber, latex, steel, resin, etc.)
    """
    lower_m = name.strip().lower()
    assembly_keywords = ["assembly", "assemblies", "module", "modules", "system", "systems"]
    part_keywords = [
        "component", "components", "seal", "seals", "gasket", "gaskets",
        "wire", "wires", "sensor", "sensors", "valve", "valves", "part", "parts"
    ]

    for kw in assembly_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower_m):
            return "assembly"

    for kw in part_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower_m):
            return "part"

    return "raw"


def infer_material_category(name: str) -> Optional[str]:
    """Infers an optional high-level material category string from keywords."""
    lower_m = name.strip().lower()
    if "rubber" in lower_m or "latex" in lower_m:
        return "rubber"
    if (
        "carbon" in lower_m
        or "chemical" in lower_m
        or "polymer" in lower_m
        or "oil" in lower_m
        or "silicone" in lower_m
        or "resin" in lower_m
        or "sealant" in lower_m
        or "compound" in lower_m
        or "adhesive" in lower_m
    ):
        return "chemicals"
    if "steel" in lower_m or "iron" in lower_m or "metal" in lower_m or "aluminum" in lower_m or "ore" in lower_m:
        return "metals"
    if "electronic" in lower_m or "sensor" in lower_m or "wire" in lower_m or "chip" in lower_m:
        return "electronics"
    return None


@dataclass
class ResolutionResult:
    """Represents the outcome of a supplier or material entity resolution query."""
    entity_id: Optional[int] = None
    canonical_name: Optional[str] = None
    match_type: Literal[
        "exact", "alias", "normalized", "fuzzy", "created", "ambiguous", "unresolved"
    ] = "unresolved"
    match_score: Optional[float] = None
    is_new: bool = False
    is_ambiguous: bool = False
    candidate_names: List[str] = field(default_factory=list)
    resolved_by: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """Returns True if the entity was successfully matched or created without ambiguity."""
        return self.entity_id is not None and not self.is_ambiguous


class EntityResolver:
    """
    Entity Resolution Engine for Suppliers and Materials in TierLens AI.
    Executes staged matching:
      1. Exact canonical name match
      2. Exact alias match
      3. Legal suffix normalization match
      4. RapidFuzz token_sort_ratio with a minimum 90% threshold
      5. Ambiguity detection (flags ambiguous if top 2 candidates score >= 85% and diff < 5%)
    """

    FUZZY_THRESHOLD: float = 0.90
    AMBIGUITY_THRESHOLD: float = 0.85
    AMBIGUITY_DELTA: float = 0.05
    MIN_SHORT_NAME_LEN: int = 3

    def _format_canonical_name(self, raw_name: str) -> str:
        """Cleans and produces canonical title casing for entity names."""
        cleaned = re.sub(r"\s+", " ", raw_name.strip())
        # Preserve acronyms like 'LLC', 'Pvt', 'Ltd', 'ABC' if already formatted
        return " ".join(word.capitalize() if word.islower() else word for word in cleaned.split(" "))

    def resolve_supplier(
        self,
        db: Session,
        name: str,
        allow_create: bool = False,
    ) -> ResolutionResult:
        """
        Resolves a supplier name against database suppliers and aliases.

        Matching Order:
          1. Exact canonical name (case-insensitive)
          2. Exact alias (case-insensitive)
          3. Legal suffix normalization match
          4. RapidFuzz token_sort_ratio >= 90% threshold
          5. Ambiguity detection (rejects auto-merge if multiple candidates score >= 85% with diff < 5%)
          6. Unknown entity creation if allow_create=True

        Returns:
          ResolutionResult with resolved entity details, score, and flags.
        """
        cleaned = name.strip() if name else ""
        if not cleaned:
            return ResolutionResult(match_type="unresolved")

        # ---------------------------------------------------------------------
        # 1. Exact Canonical Name Match
        # ---------------------------------------------------------------------
        exact_supp = db.query(Supplier).filter(func.lower(Supplier.name) == cleaned.lower()).first()
        if exact_supp:
            return ResolutionResult(
                entity_id=exact_supp.id,
                canonical_name=exact_supp.name,
                match_type="exact",
                match_score=1.0,
                is_new=False,
                is_ambiguous=False,
                resolved_by="rule",
            )

        # ---------------------------------------------------------------------
        # 2. Exact Alias Match
        # ---------------------------------------------------------------------
        exact_alias = db.query(SupplierAlias).filter(func.lower(SupplierAlias.alias) == cleaned.lower()).first()
        if exact_alias and exact_alias.supplier:
            return ResolutionResult(
                entity_id=exact_alias.supplier_id,
                canonical_name=exact_alias.supplier.name,
                match_type="alias",
                match_score=exact_alias.match_score if exact_alias.match_score is not None else 1.0,
                is_new=False,
                is_ambiguous=False,
                resolved_by=exact_alias.resolved_by or "rule",
            )

        # ---------------------------------------------------------------------
        # 3. Legal Suffix Normalization Match
        # ---------------------------------------------------------------------
        norm_query = normalize_company_name(cleaned)
        all_suppliers = db.query(Supplier).all()
        all_aliases = db.query(SupplierAlias).all()

        normalized_matched_supplier_ids: Set[int] = set()
        for supp in all_suppliers:
            if normalize_company_name(supp.name) == norm_query:
                normalized_matched_supplier_ids.add(supp.id)

        for alias_entry in all_aliases:
            if normalize_company_name(alias_entry.alias) == norm_query:
                normalized_matched_supplier_ids.add(alias_entry.supplier_id)

        if len(normalized_matched_supplier_ids) == 1:
            supp_id = next(iter(normalized_matched_supplier_ids))
            supp = db.query(Supplier).filter(Supplier.id == supp_id).first()
            if supp:
                # Preserve original extracted name as an alias if not already tracked
                existing_alias = db.query(SupplierAlias).filter(
                    SupplierAlias.supplier_id == supp.id,
                    func.lower(SupplierAlias.alias) == cleaned.lower(),
                ).first()
                if not existing_alias and cleaned.lower() != supp.name.lower():
                    new_alias = SupplierAlias(
                        supplier_id=supp.id,
                        alias=cleaned,
                        match_score=1.0,
                        resolved_by="rule",
                    )
                    db.add(new_alias)
                    db.flush()

                return ResolutionResult(
                    entity_id=supp.id,
                    canonical_name=supp.name,
                    match_type="normalized",
                    match_score=1.0,
                    is_new=False,
                    is_ambiguous=False,
                    resolved_by="rule",
                )
        elif len(normalized_matched_supplier_ids) > 1:
            candidate_names = [
                s.name for s in all_suppliers if s.id in normalized_matched_supplier_ids
            ]
            logger.warning(
                f"Ambiguous normalized match for '{cleaned}' between suppliers: {candidate_names}"
            )
            return ResolutionResult(
                is_ambiguous=True,
                match_type="ambiguous",
                candidate_names=candidate_names,
                match_score=1.0,
            )

        # ---------------------------------------------------------------------
        # 4 & 5. RapidFuzz token_sort_ratio Matching & Ambiguity Detection
        # ---------------------------------------------------------------------
        supplier_id_to_supp = {s.id: s for s in all_suppliers}
        supplier_max_scores: dict[int, float] = {}

        # Short name protection: if query root <= 3 characters, require exact match
        if len(norm_query) > self.MIN_SHORT_NAME_LEN:
            # Score canonical names
            for s in all_suppliers:
                norm_cand = normalize_company_name(s.name)
                if len(norm_cand) <= self.MIN_SHORT_NAME_LEN:
                    continue
                score = fuzz.token_sort_ratio(norm_query, norm_cand) / 100.0
                supplier_max_scores[s.id] = max(supplier_max_scores.get(s.id, 0.0), score)

            # Score aliases
            for a in all_aliases:
                norm_cand = normalize_company_name(a.alias)
                if len(norm_cand) <= self.MIN_SHORT_NAME_LEN:
                    continue
                score = fuzz.token_sort_ratio(norm_query, norm_cand) / 100.0
                supplier_max_scores[a.supplier_id] = max(
                    supplier_max_scores.get(a.supplier_id, 0.0), score
                )

        # Filter candidate suppliers scoring at least ambiguity threshold (0.85)
        qualifying_candidates: List[Tuple[int, float]] = [
            (sid, score) for sid, score in supplier_max_scores.items() if score >= self.AMBIGUITY_THRESHOLD
        ]
        qualifying_candidates.sort(key=lambda x: x[1], reverse=True)

        # Check for ambiguity: if top two candidates both score >= 85% and diff < 5%
        if len(qualifying_candidates) >= 2:
            top_sid, top_score = qualifying_candidates[0]
            second_sid, second_score = qualifying_candidates[1]

            if (top_score - second_score) < self.AMBIGUITY_DELTA:
                ambiguous_names = [
                    supplier_id_to_supp[top_sid].name,
                    supplier_id_to_supp[second_sid].name,
                ]
                logger.warning(
                    f"Ambiguous fuzzy match for '{cleaned}': '{ambiguous_names[0]}' ({top_score:.2f}) "
                    f"vs '{ambiguous_names[1]}' ({second_score:.2f})"
                )
                return ResolutionResult(
                    is_ambiguous=True,
                    match_type="ambiguous",
                    candidate_names=ambiguous_names,
                    match_score=top_score,
                )

        # Single unambiguous top candidate
        if qualifying_candidates:
            top_sid, top_score = qualifying_candidates[0]
            if top_score >= self.FUZZY_THRESHOLD:
                supp = supplier_id_to_supp[top_sid]
                # Preserve alias with match_score and resolved_by='fuzzy'
                existing_alias = db.query(SupplierAlias).filter(
                    SupplierAlias.supplier_id == supp.id,
                    func.lower(SupplierAlias.alias) == cleaned.lower(),
                ).first()
                if not existing_alias and cleaned.lower() != supp.name.lower():
                    new_alias = SupplierAlias(
                        supplier_id=supp.id,
                        alias=cleaned,
                        match_score=round(top_score, 4),
                        resolved_by="fuzzy",
                    )
                    db.add(new_alias)
                    db.flush()

                return ResolutionResult(
                    entity_id=supp.id,
                    canonical_name=supp.name,
                    match_type="fuzzy",
                    match_score=round(top_score, 4),
                    is_new=False,
                    is_ambiguous=False,
                    resolved_by="fuzzy",
                )

        # ---------------------------------------------------------------------
        # 6. Unknown Entity Creation (when allow_create=True)
        # ---------------------------------------------------------------------
        if allow_create:
            formatted_name = self._format_canonical_name(cleaned)
            # Idempotency safety: check if formatted_name already exists
            existing = db.query(Supplier).filter(func.lower(Supplier.name) == formatted_name.lower()).first()
            if existing:
                return ResolutionResult(
                    entity_id=existing.id,
                    canonical_name=existing.name,
                    match_type="exact",
                    match_score=1.0,
                    is_new=False,
                    is_ambiguous=False,
                    resolved_by="rule",
                )

            new_supplier = Supplier(
                name=formatted_name,
                entity_type="supplier",
                base_risk=0.0,
                is_active=True,
            )
            db.add(new_supplier)
            db.flush()

            # Add original extracted name as initial alias if different
            if cleaned.lower() != formatted_name.lower():
                alias_entry = SupplierAlias(
                    supplier_id=new_supplier.id,
                    alias=cleaned,
                    match_score=1.0,
                    resolved_by="rule",
                )
                db.add(alias_entry)
                db.flush()

            logger.info(f"Created new canonical supplier '{formatted_name}' (ID: {new_supplier.id})")
            return ResolutionResult(
                entity_id=new_supplier.id,
                canonical_name=new_supplier.name,
                match_type="created",
                match_score=1.0,
                is_new=True,
                is_ambiguous=False,
                resolved_by="rule",
            )

        return ResolutionResult(
            entity_id=None,
            canonical_name=None,
            match_type="unresolved",
            match_score=None,
            is_new=False,
            is_ambiguous=False,
        )

    def resolve_material(
        self,
        db: Session,
        name: str,
        allow_create: bool = False,
        unit: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Resolves a material name against existing material records.

        Matching Order:
          1. Exact canonical name match (case-insensitive)
          2. Normalized material name match
          3. RapidFuzz token_sort_ratio >= 90% threshold
          4. Ambiguity detection (rejects merge if top 2 candidates score >= 85% and diff < 5%)
          5. Unknown material creation if allow_create=True (infers material_type and category)

        Returns:
          ResolutionResult with resolved material details, score, and flags.
        """
        cleaned = name.strip() if name else ""
        if not cleaned:
            return ResolutionResult(match_type="unresolved")

        # ---------------------------------------------------------------------
        # 1. Exact Canonical Match
        # ---------------------------------------------------------------------
        exact_mat = db.query(Material).filter(func.lower(Material.name) == cleaned.lower()).first()
        if exact_mat:
            return ResolutionResult(
                entity_id=exact_mat.id,
                canonical_name=exact_mat.name,
                match_type="exact",
                match_score=1.0,
                is_new=False,
                is_ambiguous=False,
                resolved_by="rule",
            )

        # ---------------------------------------------------------------------
        # 2. Normalized Name Match
        # ---------------------------------------------------------------------
        norm_query = normalize_material_name(cleaned)
        all_materials = db.query(Material).all()

        normalized_matches = [m for m in all_materials if normalize_material_name(m.name) == norm_query]
        if len(normalized_matches) == 1:
            matched_mat = normalized_matches[0]
            return ResolutionResult(
                entity_id=matched_mat.id,
                canonical_name=matched_mat.name,
                match_type="normalized",
                match_score=1.0,
                is_new=False,
                is_ambiguous=False,
                resolved_by="rule",
            )
        elif len(normalized_matches) > 1:
            candidate_names = [m.name for m in normalized_matches]
            logger.warning(f"Ambiguous normalized material match for '{cleaned}': {candidate_names}")
            return ResolutionResult(
                is_ambiguous=True,
                match_type="ambiguous",
                candidate_names=candidate_names,
                match_score=1.0,
            )

        # ---------------------------------------------------------------------
        # 3. RapidFuzz token_sort_ratio Matching & Ambiguity Detection
        # ---------------------------------------------------------------------
        material_scores: List[Tuple[Material, float]] = []
        for m in all_materials:
            norm_cand = normalize_material_name(m.name)
            if not norm_cand:
                continue
            score = fuzz.token_sort_ratio(norm_query, norm_cand) / 100.0
            if score >= self.AMBIGUITY_THRESHOLD:
                material_scores.append((m, score))

        material_scores.sort(key=lambda x: x[1], reverse=True)

        if len(material_scores) >= 2:
            top_m, top_score = material_scores[0]
            second_m, second_score = material_scores[1]
            if (top_score - second_score) < self.AMBIGUITY_DELTA:
                ambiguous_names = [top_m.name, second_m.name]
                logger.warning(
                    f"Ambiguous fuzzy material match for '{cleaned}': '{top_m.name}' ({top_score:.2f}) "
                    f"vs '{second_m.name}' ({second_score:.2f})"
                )
                return ResolutionResult(
                    is_ambiguous=True,
                    match_type="ambiguous",
                    candidate_names=ambiguous_names,
                    match_score=top_score,
                )

        if material_scores:
            top_m, top_score = material_scores[0]
            if top_score >= self.FUZZY_THRESHOLD:
                return ResolutionResult(
                    entity_id=top_m.id,
                    canonical_name=top_m.name,
                    match_type="fuzzy",
                    match_score=round(top_score, 4),
                    is_new=False,
                    is_ambiguous=False,
                    resolved_by="fuzzy",
                )

        # ---------------------------------------------------------------------
        # 4. Unknown Material Creation (when allow_create=True)
        # ---------------------------------------------------------------------
        if allow_create:
            formatted_name = self._format_canonical_name(cleaned)
            existing = db.query(Material).filter(func.lower(Material.name) == formatted_name.lower()).first()
            if existing:
                return ResolutionResult(
                    entity_id=existing.id,
                    canonical_name=existing.name,
                    match_type="exact",
                    match_score=1.0,
                    is_new=False,
                    is_ambiguous=False,
                    resolved_by="rule",
                )

            mat_type = infer_material_type(cleaned)
            mat_category = infer_material_category(cleaned)

            new_material = Material(
                name=formatted_name,
                material_type=mat_type,
                unit=unit,
                category=mat_category,
            )
            db.add(new_material)
            db.flush()

            logger.info(
                f"Created new canonical material '{formatted_name}' (ID: {new_material.id}, "
                f"type: {mat_type}, category: {mat_category})"
            )
            return ResolutionResult(
                entity_id=new_material.id,
                canonical_name=new_material.name,
                match_type="created",
                match_score=1.0,
                is_new=True,
                is_ambiguous=False,
                resolved_by="rule",
            )

        return ResolutionResult(
            entity_id=None,
            canonical_name=None,
            match_type="unresolved",
            match_score=None,
            is_new=False,
            is_ambiguous=False,
        )

    def resolve_or_create_supplier(self, db: Session, name: str) -> Supplier:
        """
        Resolves a supplier name or creates a new supplier if genuinely unknown.
        Raises ValueError if resolution is ambiguous or fails.
        """
        res = self.resolve_supplier(db=db, name=name, allow_create=True)
        if res.is_ambiguous:
            raise ValueError(
                f"Cannot resolve or create supplier '{name}': ambiguous match between {res.candidate_names}"
            )
        if not res.entity_id:
            raise ValueError(f"Failed to resolve or create supplier '{name}'")

        supplier = db.query(Supplier).filter(Supplier.id == res.entity_id).first()
        if not supplier:
            raise ValueError(f"Supplier with ID {res.entity_id} not found in database session")
        return supplier

    def resolve_or_create_material(
        self,
        db: Session,
        name: str,
        unit: Optional[str] = None,
    ) -> Material:
        """
        Resolves a material name or creates a new material if genuinely unknown.
        Raises ValueError if resolution is ambiguous or fails.
        """
        res = self.resolve_material(db=db, name=name, allow_create=True, unit=unit)
        if res.is_ambiguous:
            raise ValueError(
                f"Cannot resolve or create material '{name}': ambiguous match between {res.candidate_names}"
            )
        if not res.entity_id:
            raise ValueError(f"Failed to resolve or create material '{name}'")

        material = db.query(Material).filter(Material.id == res.entity_id).first()
        if not material:
            raise ValueError(f"Material with ID {res.entity_id} not found in database session")
        return material


# Default singleton instance for convenient import
entity_resolver = EntityResolver()
