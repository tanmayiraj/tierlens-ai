# TierLens AI: API Specification

**Version:** 0.1 (Prototype)
**Companions:** `PRD.md`, `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`
**Style:** REST over HTTP, JSON bodies
**Framework:** FastAPI (interactive docs auto-generated at `/docs` and `/redoc`)
**Base URL (local):** `http://localhost:8000/api/v1`

---

## 1. Conventions

### 1.1 General
| Item | Convention |
|---|---|
| Format | JSON (`Content-Type: application/json`), except file upload (`multipart/form-data`) |
| Naming | `snake_case` for fields, plural nouns for collections |
| IDs | Integers (matching `DATABASE_SCHEMA.md`) |
| Dates | ISO 8601 (`2026-11-18` or `2026-11-18T10:30:00Z`) |
| Currency | Plain numbers in a single configured currency (default INR) |
| Auth (prototype) | None. Future: `Authorization: Bearer <token>` |

### 1.2 Pagination
List endpoints accept `limit` (default 50, max 200) and `offset` (default 0).

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

### 1.3 Error Format
All errors use one shape:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Supplier 99 does not exist.",
    "details": {}
  }
}
```

| HTTP | Code | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed input |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `CONFLICT` | Duplicate or invalid state change |
| 413 | `FILE_TOO_LARGE` | Upload exceeds limit |
| 415 | `UNSUPPORTED_FILE_TYPE` | Not PDF, TXT or CSV |
| 422 | `VALIDATION_ERROR` | Field-level validation failed |
| 502 | `LLM_UNAVAILABLE` | Extraction service could not reach the LLM |
| 500 | `INTERNAL_ERROR` | Unexpected failure |

### 1.4 Shared Enums

| Enum | Values |
|---|---|
| `node_type` | `supplier`, `material`, `line`, `product` |
| `doc_type` | `purchase_order`, `supplier_record`, `contract`, `invoice`, `procurement_note` |
| `extraction_status` | `pending`, `processing`, `done`, `failed` |
| `relationship_status` | `pending`, `approved`, `rejected` |
| `event_type` | `shutdown`, `delay`, `shortage`, `transport`, `natural_disaster`, `quality` |
| `severity_label` | `low`, `medium`, `high`, `critical` |
| `alert_status` | `open`, `acknowledged`, `resolved` |
| `mitigation_type` | `alternate_supplier`, `safety_stock`, `reroute`, `expedite` |

---

## 2. Component Communication Overview

```
Frontend ──REST──> API Layer ──calls──> Services (in-process Python modules)
                                         ├─ Extraction ──HTTPS──> LLM API
                                         ├─ Graph (NetworkX, in memory)
                                         ├─ Risk Engine
                                         ├─ Simulation Engine
                                         └─ Recommender
                                         All ──SQLAlchemy──> SQLite
```

- The frontend only talks to the REST API.
- The API layer calls internal services directly (no network hop in the prototype).
- Only the Extraction and Alert-explanation steps call an external LLM.
- Long-running work (document extraction) runs as a background task. The client polls for status.

---

## 3. Endpoints Summary

| # | Method | Path | Purpose |
|---|---|---|---|
| 1 | GET | `/health` | Service health check |
| 2 | POST | `/documents/upload` | Upload documents and start extraction |
| 3 | GET | `/documents` | List documents |
| 4 | GET | `/documents/{id}` | Document details and extraction status |
| 5 | GET | `/documents/{id}/evidence` | Facts extracted from a document |
| 6 | POST | `/documents/load-samples` | Load bundled sample documents |
| 7 | GET | `/relationships` | List relationships (filter by status, tier) |
| 8 | GET | `/review-queue` | Pending low-confidence relationships |
| 9 | POST | `/review/{relationship_id}` | Approve, reject or correct a relationship |
| 10 | GET | `/suppliers` | List suppliers |
| 11 | GET | `/suppliers/{id}` | Supplier details |
| 12 | POST | `/graph/rebuild` | Rebuild graph from approved data |
| 13 | GET | `/graph` | Nodes and edges for visualisation |
| 14 | GET | `/graph/node/{node_type}/{id}` | Node detail with evidence and risk |
| 15 | GET | `/dependencies` | Hidden dependencies and single points of failure |
| 16 | POST | `/events` | Log a disruption event |
| 17 | GET | `/events` | List events |
| 18 | GET | `/alerts` | List alerts |
| 19 | GET | `/alerts/{id}` | Alert detail |
| 20 | PATCH | `/alerts/{id}` | Update alert status |
| 21 | GET | `/impact/{event_id}` | Downstream impact of an event |
| 22 | POST | `/simulate` | Run a what-if scenario |
| 23 | GET | `/scenarios` | List saved scenarios |
| 24 | GET | `/scenarios/{id}` | Scenario with results |
| 25 | GET | `/alternatives/{supplier_id}` | Ranked alternative suppliers |
| 26 | GET | `/risk/summary` | Dashboard-level risk summary |

---

## 4. Endpoint Details

### 4.1 System

#### `GET /health`
**Response 200**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "connected",
  "graph": { "nodes": 42, "edges": 61, "last_built": "2026-11-18T10:30:00Z" },
  "llm": "configured"
}
```

---

### 4.2 Documents and Extraction

#### `POST /documents/upload`
Upload one or more files. Extraction starts automatically in the background.

**Request:** `multipart/form-data`
| Field | Type | Required | Notes |
|---|---|---|---|
| files | file[] | Yes | PDF, TXT or CSV, max 10 MB each |
| doc_type | string | No | Defaults to auto-detect |

**Response 202**
```json
{
  "documents": [
    { "id": 12, "filename": "PO_1042.pdf", "extraction_status": "pending" }
  ]
}
```

#### `POST /documents/load-samples`
Loads the bundled synthetic dataset from `data/sample_docs/` and queues extraction.

**Response 202**
```json
{ "loaded": 10, "queued_for_extraction": 10 }
```

#### `GET /documents`
**Query:** `extraction_status`, `doc_type`, `limit`, `offset`

**Response 200**
```json
{
  "items": [
    {
      "id": 12,
      "filename": "PO_1042.pdf",
      "doc_type": "purchase_order",
      "extraction_status": "done",
      "uploaded_at": "2026-11-18T09:12:00Z",
      "relationships_found": 4
    }
  ],
  "total": 10, "limit": 50, "offset": 0
}
```

#### `GET /documents/{id}`
**Response 200**
```json
{
  "id": 12,
  "filename": "PO_1042.pdf",
  "doc_type": "purchase_order",
  "page_count": 2,
  "extraction_status": "done",
  "uploaded_at": "2026-11-18T09:12:00Z",
  "stats": { "entities": 6, "relationships": 4, "low_confidence": 1 }
}
```
Clients poll this endpoint while `extraction_status` is `pending` or `processing`.

#### `GET /documents/{id}/evidence`
**Response 200**
```json
{
  "document_id": 12,
  "evidence": [
    {
      "id": 77,
      "page": 1,
      "snippet": "GreenLatex to supply 40 MT of natural latex to RubberCore monthly.",
      "llm_confidence": 0.92,
      "relationship": {
        "id": 31,
        "supplier": "GreenLatex Pvt Ltd",
        "buyer": "RubberCore Industries",
        "material": "Natural Latex"
      }
    }
  ]
}
```

---

### 4.3 Relationships and Review

#### `GET /relationships`
**Query:** `status`, `tier`, `material_id`, `supplier_id`, `min_confidence`, `limit`, `offset`

**Response 200**
```json
{
  "items": [
    {
      "id": 31,
      "supplier": { "id": 7, "name": "GreenLatex Pvt Ltd" },
      "buyer": { "id": 4, "name": "RubberCore Industries" },
      "material": { "id": 3, "name": "Natural Latex" },
      "tier": 3,
      "lead_time_days": 21,
      "share_pct": 70,
      "inventory_days": 5,
      "confidence": 0.92,
      "status": "approved",
      "evidence_count": 2
    }
  ],
  "total": 1, "limit": 50, "offset": 0
}
```

#### `GET /review-queue`
Pending relationships, lowest confidence first.

**Response 200**
```json
{
  "items": [
    {
      "relationship_id": 45,
      "supplier": "PetroChem Asia",
      "buyer": "RubberCore",
      "material": "Carbon Black",
      "confidence": 0.58,
      "snippet": "...carbon black from PetroChem or a similar vendor...",
      "document": "Procurement_Note_07.txt"
    }
  ],
  "total": 3
}
```

#### `POST /review/{relationship_id}`
Approve, reject, or correct then approve.

**Request**
```json
{
  "action": "approve",
  "corrections": {
    "share_pct": 60,
    "lead_time_days": 14
  },
  "reviewed_by": "analyst_1"
}
```
`action` is one of `approve`, `reject`. `corrections` is optional and applies before approval.

**Response 200**
```json
{
  "id": 45,
  "status": "approved",
  "graph_rebuild_required": true
}
```

---

### 4.4 Suppliers

#### `GET /suppliers`
**Query:** `tier`, `region`, `min_risk`, `q` (name search), `limit`, `offset`

**Response 200**
```json
{
  "items": [
    {
      "id": 7,
      "name": "GreenLatex Pvt Ltd",
      "country": "India",
      "region": "South Asia",
      "tier": 3,
      "risk_score": 62.5,
      "materials": ["Natural Latex"]
    }
  ],
  "total": 18, "limit": 50, "offset": 0
}
```

#### `GET /suppliers/{id}`
**Response 200**
```json
{
  "id": 7,
  "name": "GreenLatex Pvt Ltd",
  "aliases": ["GreenLatex", "Green Latex Pvt. Ltd."],
  "country": "India",
  "region": "South Asia",
  "capacity_per_month": 120,
  "base_risk": 35,
  "tier": 3,
  "supplies_to": [ { "id": 4, "name": "RubberCore Industries", "material": "Natural Latex" } ],
  "supplied_by": [],
  "materials": [ { "id": 3, "name": "Natural Latex", "qualified": true } ]
}
```

---

### 4.5 Graph

#### `POST /graph/rebuild`
Rebuilds the in-memory graph from approved relationships, recomputes tiers and reruns dependency analysis.

**Response 200**
```json
{ "nodes": 42, "edges": 61, "max_tier": 3, "built_at": "2026-11-18T10:30:00Z" }
```

#### `GET /graph`
**Query**
| Param | Type | Notes |
|---|---|---|
| tier_max | int | Include tiers up to this value |
| region | string | |
| material_id | int | Only chains involving this material |
| min_risk | number | |
| include_pending | bool | Draw pending relationships as dashed edges |

**Response 200**
```json
{
  "nodes": [
    {
      "id": "supplier:7",
      "type": "supplier",
      "label": "GreenLatex Pvt Ltd",
      "tier": 3,
      "region": "South Asia",
      "risk_score": 62.5,
      "flags": ["hidden_dependency", "single_source"]
    },
    {
      "id": "line:1",
      "type": "line",
      "label": "Line A (Sedan X)",
      "tier": 0,
      "risk_score": 40.0,
      "flags": []
    }
  ],
  "edges": [
    {
      "id": "rel:31",
      "source": "supplier:7",
      "target": "supplier:4",
      "material": "Natural Latex",
      "lead_time_days": 21,
      "share_pct": 70,
      "confidence": 0.92,
      "status": "approved"
    }
  ],
  "meta": { "built_at": "2026-11-18T10:30:00Z" }
}
```

#### `GET /graph/node/{node_type}/{id}`
**Response 200**
```json
{
  "id": "supplier:7",
  "type": "supplier",
  "label": "GreenLatex Pvt Ltd",
  "tier": 3,
  "risk_score": 62.5,
  "risk_breakdown": {
    "event_severity": 0,
    "criticality": 22,
    "single_source_exposure": 20,
    "buffer_gap": 12,
    "regional_risk": 8.5
  },
  "upstream": [],
  "downstream": [
    { "id": "supplier:4", "label": "RubberCore Industries", "material": "Natural Latex" }
  ],
  "reaches": {
    "tier1_suppliers": ["TyreWorks Ltd", "GripSeal Components"],
    "production_lines": ["Line A", "Line B"]
  },
  "evidence": [
    { "document": "PO_1042.pdf", "page": 1, "snippet": "GreenLatex to supply 40 MT..." }
  ]
}
```

#### `GET /dependencies`
Hidden dependencies and structural weaknesses.

**Query:** `type` (optional filter), `min_severity`

**Response 200**
```json
{
  "items": [
    {
      "id": "dep-1",
      "type": "shared_upstream_supplier",
      "supplier": { "id": 4, "name": "RubberCore Industries", "tier": 2 },
      "description": "Feeds 2 Tier 1 suppliers (TyreWorks, GripSeal), which supply 3 production lines.",
      "affected_tier1": ["TyreWorks Ltd", "GripSeal Components"],
      "affected_lines": ["Line A", "Line B", "Line C"],
      "severity": "high"
    },
    {
      "id": "dep-2",
      "type": "single_source_material",
      "material": { "id": 3, "name": "Natural Latex" },
      "supplier": { "id": 7, "name": "GreenLatex Pvt Ltd", "tier": 3 },
      "description": "Only one supplier of Natural Latex on this chain.",
      "severity": "high"
    }
  ],
  "total": 2
}
```

`type` values: `shared_upstream_supplier`, `single_point_of_failure`, `single_source_material`, `concentration_risk`, `deep_hidden_chain`.

---

### 4.6 Events and Alerts

#### `POST /events`
Logs a disruption and automatically generates an alert.

**Request**
```json
{
  "supplier_id": 7,
  "event_type": "shutdown",
  "severity": 5,
  "start_date": "2026-11-20",
  "expected_duration_days": 30,
  "description": "Factory closed after flooding.",
  "source": "simulated",
  "is_simulated": true
}
```

**Response 201**
```json
{
  "event_id": 3,
  "alert_id": 9,
  "severity_label": "critical",
  "risk_score": 83
}
```

#### `GET /events`
**Query:** `supplier_id`, `event_type`, `is_simulated`, `limit`, `offset`

**Response 200**
```json
{
  "items": [
    {
      "id": 3,
      "supplier": { "id": 7, "name": "GreenLatex Pvt Ltd" },
      "event_type": "shutdown",
      "severity": 5,
      "start_date": "2026-11-20",
      "expected_duration_days": 30,
      "is_simulated": true
    }
  ],
  "total": 1, "limit": 50, "offset": 0
}
```

#### `GET /alerts`
**Query:** `status`, `severity_label`, `supplier_id`, `sort` (default `risk_score:desc`), `limit`, `offset`

**Response 200**
```json
{
  "items": [
    {
      "id": 9,
      "event_id": 3,
      "supplier": "GreenLatex Pvt Ltd",
      "severity_label": "critical",
      "risk_score": 83,
      "days_to_impact": 9,
      "revenue_at_risk": 1850000,
      "status": "open",
      "created_at": "2026-11-18T10:45:00Z"
    }
  ],
  "total": 1, "limit": 50, "offset": 0
}
```

#### `GET /alerts/{id}`
**Response 200**
```json
{
  "id": 9,
  "event": {
    "id": 3,
    "supplier": "GreenLatex Pvt Ltd",
    "event_type": "shutdown",
    "expected_duration_days": 30
  },
  "severity_label": "critical",
  "risk_score": 83,
  "score_breakdown": {
    "event_severity": 24,
    "criticality": 22,
    "single_source_exposure": 20,
    "buffer_gap": 12,
    "regional_risk": 5,
    "total": 83
  },
  "days_to_impact": 9,
  "revenue_at_risk": 1850000,
  "explanation": "GreenLatex is the only latex source for RubberCore. With about 9 days of buffer and a 30-day shutdown, tyre supply to Line A and Line B is likely to stop.",
  "affected": [
    { "node_type": "supplier", "name": "RubberCore Industries", "path_depth": 1, "days_to_impact": 5 },
    { "node_type": "supplier", "name": "TyreWorks Ltd", "path_depth": 2, "days_to_impact": 9 },
    { "node_type": "line", "name": "Line A", "path_depth": 3, "days_to_impact": 9 }
  ],
  "evidence": [
    { "document": "PO_1042.pdf", "page": 1, "snippet": "GreenLatex to supply 40 MT..." }
  ],
  "alternatives_url": "/api/v1/alternatives/7",
  "status": "open"
}
```

#### `PATCH /alerts/{id}`
**Request**
```json
{ "status": "acknowledged" }
```
**Response 200**
```json
{ "id": 9, "status": "acknowledged" }
```

---

### 4.7 Impact Analysis

#### `GET /impact/{event_id}`
Full downstream trace for an event.

**Response 200**
```json
{
  "event_id": 3,
  "origin": { "id": "supplier:7", "label": "GreenLatex Pvt Ltd", "tier": 3 },
  "summary": {
    "suppliers_affected": 3,
    "materials_affected": 2,
    "lines_affected": 2,
    "products_affected": 1,
    "first_impact_in_days": 5,
    "revenue_at_risk": 1850000
  },
  "paths": [
    {
      "nodes": ["GreenLatex Pvt Ltd", "RubberCore Industries", "TyreWorks Ltd", "Line A"],
      "days_to_impact": 9
    }
  ],
  "affected_nodes": [
    { "node_type": "line", "id": 1, "name": "Line A", "days_to_impact": 9 }
  ]
}
```

---

### 4.8 What-If Simulation

#### `POST /simulate`
Runs on a copy of the graph. Nothing in live data changes unless `save` is true.

**Request**
```json
{
  "name": "GreenLatex 30-day outage",
  "failed_supplier_ids": [7],
  "duration_days": 30,
  "mitigations": [
    { "type": "alternate_supplier", "material_id": 3, "supplier_id": 12 },
    { "type": "safety_stock", "material_id": 3, "extra_days": 10 }
  ],
  "save": true
}
```

**Mitigation shapes**
| Type | Fields |
|---|---|
| `alternate_supplier` | `material_id`, `supplier_id`, optional `share_pct` |
| `safety_stock` | `material_id`, `extra_days` |
| `reroute` | `from_supplier_id`, `to_supplier_id`, `material_id` |
| `expedite` | `supplier_id`, `lead_time_reduction_days` |

**Response 200**
```json
{
  "scenario_id": 5,
  "before_mitigation": {
    "lines_at_risk": 2,
    "revenue_at_risk": 1850000,
    "days_to_impact": 9,
    "affected_path": ["GreenLatex", "RubberCore", "TyreWorks", "Line A"]
  },
  "after_mitigation": {
    "lines_at_risk": 0,
    "revenue_at_risk": 0,
    "days_to_impact": null,
    "affected_path": []
  },
  "improvement": {
    "revenue_protected": 1850000,
    "lines_protected": 2
  },
  "notes": ["Alternate supplier lead time (14 days) exceeds current buffer; safety stock bridges the gap."]
}
```
`days_to_impact: null` means the disruption is absorbed by buffers.

#### `GET /scenarios`
**Response 200**
```json
{
  "items": [
    { "id": 5, "name": "GreenLatex 30-day outage", "duration_days": 30, "created_at": "2026-11-18T11:00:00Z" }
  ],
  "total": 1
}
```

#### `GET /scenarios/{id}`
Returns the scenario definition plus its stored `before_mitigation` and `after_mitigation` results (same shape as the `/simulate` response).

---

### 4.9 Alternative Suppliers

#### `GET /alternatives/{supplier_id}`
**Query:** `material_id` (optional), `limit` (default 5)

**Response 200**
```json
{
  "failed_supplier": { "id": 7, "name": "GreenLatex Pvt Ltd" },
  "material": { "id": 3, "name": "Natural Latex" },
  "alternatives": [
    {
      "supplier": { "id": 12, "name": "SouthAsia Latex Co" },
      "rank": 1,
      "score": 0.84,
      "lead_time_days": 14,
      "capacity_per_month": 90,
      "region_risk": "low",
      "qualified": true,
      "existing_relationship": false,
      "reasons": [
        "Qualified for Natural Latex",
        "Shorter lead time than current supplier",
        "Located in a lower-risk region"
      ]
    }
  ]
}
```

---

### 4.10 Dashboard

#### `GET /risk/summary`
**Response 200**
```json
{
  "network": { "suppliers": 18, "tier1": 5, "tier2": 7, "tier3": 6 },
  "hidden_dependencies": 4,
  "single_source_materials": 3,
  "open_alerts": { "critical": 1, "high": 2, "medium": 1, "low": 0 },
  "top_risky_suppliers": [
    { "id": 7, "name": "GreenLatex Pvt Ltd", "tier": 3, "risk_score": 83 }
  ],
  "total_revenue_at_risk": 1850000
}
```

---

## 5. Typical Call Sequences

### 5.1 Build the supplier map
```
POST /documents/load-samples
GET  /documents/{id}            (poll until extraction_status = done)
GET  /review-queue
POST /review/{relationship_id}  (approve or correct each)
POST /graph/rebuild
GET  /graph
GET  /dependencies
```

### 5.2 Respond to a disruption
```
POST /events
GET  /alerts/{alert_id}
GET  /impact/{event_id}
GET  /alternatives/{supplier_id}
```

### 5.3 What-if planning
```
POST /simulate  (no mitigations)  → see baseline exposure
POST /simulate  (with mitigations) → compare
GET  /scenarios/{id}
```

---

## 6. Frontend Screen to Endpoint Mapping

| Screen | Endpoints used |
|---|---|
| Dashboard | `/risk/summary`, `/alerts`, `/dependencies` |
| Upload and Review | `/documents/upload`, `/documents/{id}`, `/review-queue`, `/review/{id}` |
| Graph Explorer | `/graph`, `/graph/node/{type}/{id}`, `/dependencies` |
| Alerts | `/alerts`, `/alerts/{id}`, `/impact/{event_id}` |
| What-If Lab | `/simulate`, `/scenarios`, `/alternatives/{id}`, `/suppliers` |

---

## 7. Non-Functional Notes

| Topic | Decision |
|---|---|
| **Async work** | Extraction runs via FastAPI `BackgroundTasks`. Replace with a task queue later |
| **Performance targets** | Graph, impact and simulation responses under 1 second for ~100 nodes |
| **Idempotency** | `POST /graph/rebuild` is safe to call repeatedly |
| **CORS** | Allow `http://localhost:5173` in the prototype |
| **Rate limiting** | Not needed for the prototype. Add per-client limits before exposing publicly |
| **Versioning** | URL prefix (`/api/v1`). Breaking changes go to `/api/v2` |
| **Validation** | Pydantic models validate all request and response bodies |
| **LLM failures** | Return `502 LLM_UNAVAILABLE` for extraction triggers, and fall back to a template explanation for alerts so alerts are never blocked |

---

## 8. Pydantic Model Sketches

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

class EventCreate(BaseModel):
    supplier_id: int
    event_type: Literal["shutdown","delay","shortage","transport","natural_disaster","quality"]
    severity: int = Field(ge=1, le=5)
    start_date: date
    expected_duration_days: Optional[int] = None
    description: Optional[str] = None
    source: Optional[str] = "simulated"
    is_simulated: bool = True

class Mitigation(BaseModel):
    type: Literal["alternate_supplier","safety_stock","reroute","expedite"]
    material_id: Optional[int] = None
    supplier_id: Optional[int] = None
    from_supplier_id: Optional[int] = None
    to_supplier_id: Optional[int] = None
    extra_days: Optional[int] = None
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    lead_time_reduction_days: Optional[int] = None

class SimulationRequest(BaseModel):
    name: Optional[str] = None
    failed_supplier_ids: list[int]
    duration_days: int = Field(gt=0)
    mitigations: list[Mitigation] = []
    save: bool = False

class ReviewRequest(BaseModel):
    action: Literal["approve","reject"]
    corrections: Optional[dict] = None
    reviewed_by: Optional[str] = None
```
