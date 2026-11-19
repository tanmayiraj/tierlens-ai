# TierLens AI: Architecture

**Version:** 0.1 (Prototype)
**Companion to:** `PRD.md`

This document describes how TierLens AI will be built: components, data flow, data model, algorithms, API, project structure and key technical decisions.

---

## 1. Architecture Goals

| Goal | What it means |
|---|---|
| **Explainable** | Every node, edge and alert traces back to a source document and a scoring breakdown |
| **Simple to demo** | Runs locally with one command, on synthetic sample data |
| **Modular** | Extraction, graph, risk, simulation and API are separate, swappable modules |
| **Deterministic where it matters** | LLM is used only for extraction and explanations. Graph traversal, scoring and simulation are plain, testable code |
| **Extensible** | Easy to add live data feeds, a graph database or ERP connectors later |

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND (Web UI)                     │
│  Graph Explorer │ Alerts Panel │ Impact View │ What-If Lab   │
└──────────────────────────────┬───────────────────────────────┘
                               │ REST / JSON
┌──────────────────────────────▼───────────────────────────────┐
│                       API LAYER (FastAPI)                    │
│  /documents  /graph  /dependencies  /events  /alerts         │
│  /impact  /simulate  /alternatives                           │
└───┬─────────────┬──────────────┬──────────────┬──────────────┘
    │             │              │              │
┌───▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌─────▼──────────┐
│Extraction│ │  Graph   │ │ Risk Engine │ │  Simulation    │
│ Service  │ │  Service │ │ + Alerting  │ │  Engine        │
└───┬──────┘ └────┬─────┘ └──────┬──────┘ └─────┬──────────┘
    │             │              │              │
    │        ┌────▼──────────────▼──────────────▼───┐
    │        │      Knowledge Graph (NetworkX)      │
    │        └────┬─────────────────────────────────┘
    │             │
┌───▼─────────────▼────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  SQLite (entities, evidence, events, alerts)  │  Raw docs    │
└──────────────────────────────────────────────────────────────┘
        ▲
        │  LLM API (extraction + alert explanations)
```

---

## 3. Components

### 3.1 Document Ingestion
- **Input:** PDF, TXT, CSV (purchase orders, supplier records, procurement notes).
- **Steps:** load → extract text (pdfplumber / pandas for CSV) → split into chunks → store raw text with a `doc_id`.
- **Output:** normalised text chunks with source metadata (file name, page, chunk index).

### 3.2 Extraction Service (AI)
- Sends each chunk to an LLM with a structured-output prompt.
- Extracts:
  - **Entities:** supplier, material/component, plant, production line, location
  - **Relationships:** `supplier A --supplies [material, lead time, share %]--> buyer B`
- Each extracted fact carries: `confidence`, `source_doc_id`, `source_snippet`.
- Output is validated against a Pydantic schema. Invalid or low-confidence items go to a **review queue**.

**Extraction output (example):**
```json
{
  "relationships": [
    {
      "supplier": "GreenLatex Pvt Ltd",
      "buyer": "RubberCore Industries",
      "material": "Natural Latex",
      "lead_time_days": 21,
      "share_pct": 70,
      "confidence": 0.92,
      "source_doc": "PO_1042.pdf",
      "snippet": "GreenLatex to supply 40 MT of natural latex..."
    }
  ]
}
```

### 3.3 Entity Resolution
- Merges duplicates such as "ABC Rubber Pvt Ltd" and "ABC Rubber".
- Approach: normalise names (case, suffixes like Ltd/Inc/Pvt) → fuzzy match (RapidFuzz) → optional LLM tie-break for borderline pairs.
- Keeps an alias table so the original names remain traceable.

### 3.4 Graph Service
- Builds a **directed graph** in NetworkX, with edges pointing in the direction of material flow (upstream → downstream).
- Node types: `Supplier`, `Material`, `Component`, `Plant`, `ProductionLine`, `Product`.
- Computes tiers by distance from the manufacturer node (Tier 1 = direct supplier, Tier 2 = supplier of Tier 1, and so on).
- Exposes graph data to the frontend as nodes/edges JSON.

### 3.5 Dependency Analyzer
Detects hidden risk structure in the graph:

| Pattern | How it is detected |
|---|---|
| **Shared upstream supplier** | Tier 2/3 node with out-degree ≥ 2 into different Tier 1 chains |
| **Single point of failure** | Articulation point or the only supplier of a material on a path to a line |
| **Single-source material** | Material with exactly one supplier |
| **Concentration risk** | High share of a material or region coming from one node |
| **Deep hidden chain** | Critical path where Tier 2+ suppliers have no direct relationship with the manufacturer |

### 3.6 Risk Engine
Produces a 0 to 100 score for each supplier, as described in the PRD:

```
Risk = w1·EventSeverity + w2·Criticality + w3·SingleSourceExposure
     + w4·BufferGap + w5·RegionalRisk
```

- **Criticality:** number of downstream components/lines reachable from the node (weighted by revenue contribution).
- **BufferGap:** `max(0, disruption_days − (inventory_days + lead_time_days))`, normalised.
- Weights live in a config file so they can be tuned.
- Every score stores its **factor breakdown** for explainability.

### 3.7 Alerting
- Triggered when a disruption event is ingested or a simulation runs.
- Builds an alert object: affected nodes, severity, time-to-impact, score breakdown and linked evidence.
- The LLM turns the structured alert into a short plain-language explanation. It receives only the computed facts and does not decide the facts.

### 3.8 Simulation Engine
- Works on a **copy** of the graph so the live graph is never changed.
- Steps:
  1. Mark target node(s) as failed for N days.
  2. Propagate downstream using BFS, tracking when each node runs out of buffer.
  3. Compute the impacted components, lines and products plus the revenue at risk.
  4. Apply selected mitigations (alternate supplier, safety stock, rerouting) and recompute.
  5. Return a before/after comparison.

### 3.9 Alternative Supplier Recommender
- Filters suppliers that provide the same material or capability.
- Ranks by weighted score: lead time, capacity, region risk, existing relationship and current risk score.
- Returns a short reason for each suggestion.

### 3.10 Frontend
- **Graph Explorer:** interactive network (Cytoscape.js or vis-network). Colour by risk, shape or layer by tier. Click for node details and evidence.
- **Alerts Panel:** ranked list with severity and explanation.
- **Impact View:** downstream tree/Sankey from the disrupted node to the production line.
- **What-If Lab:** choose supplier, duration and mitigations, then compare results.

---

## 4. Data Model

### 4.1 Relational tables (SQLite)

```
suppliers(id, name, location, region, capacity, base_risk)
materials(id, name, type)
documents(id, filename, doc_type, uploaded_at)
evidence(id, doc_id, snippet, page, confidence)
relationships(id, supplier_id, buyer_id, material_id, lead_time_days,
              share_pct, inventory_days, confidence, evidence_id)
production_lines(id, plant, product, daily_revenue)
line_requirements(line_id, material_id, qty_per_day)
events(id, supplier_id, type, severity, start_date, duration_days, source)
alerts(id, event_id, severity, score, breakdown_json, explanation, created_at)
```

### 4.2 In-memory graph (NetworkX)

```
Node attrs : id, type, name, tier, location, risk_score
Edge attrs : material, lead_time_days, share_pct, inventory_days,
             confidence, evidence_id
```

The graph is rebuilt from the database on startup and after every approved extraction.

---

## 5. Key Data Flows

### 5.1 Build the network
```
Upload docs → Ingest/chunk → LLM extraction → Validate → Entity resolution
→ Review queue (low confidence) → Save to DB → Build NetworkX graph
→ Compute tiers → Run dependency analysis → Serve to UI
```

### 5.2 Disruption alert
```
Event created → Locate node → Downstream BFS → Collect affected
suppliers/components/lines → Compute time-to-impact + risk score
→ Find alternatives → Generate explanation → Store + display alert
```

### 5.3 What-if simulation
```
User picks scenario → Clone graph → Apply failure → Propagate
→ (Optional) apply mitigations → Recompute → Return before/after
```

---

## 6. API Design

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/documents/upload` | Upload documents and trigger extraction |
| GET | `/documents/{id}/evidence` | View extracted facts and source snippets |
| GET | `/graph` | Nodes and edges (filters: tier, region, risk) |
| GET | `/graph/node/{id}` | Node details, evidence, risk breakdown |
| GET | `/dependencies` | Hidden dependencies and single points of failure |
| POST | `/events` | Log a (simulated) disruption event |
| GET | `/alerts` | List alerts, ranked by severity |
| GET | `/impact/{event_id}` | Affected suppliers, components, lines |
| POST | `/simulate` | Run a what-if scenario with optional mitigations |
| GET | `/alternatives/{supplier_id}` | Ranked alternative suppliers |
| POST | `/review/{relationship_id}` | Approve or correct an extracted relationship |

**Example `/simulate` request:**
```json
{
  "failed_suppliers": ["GreenLatex Pvt Ltd"],
  "duration_days": 30,
  "mitigations": [
    { "type": "alternate_supplier", "supplier": "SouthAsia Latex Co" },
    { "type": "safety_stock", "material": "Natural Latex", "extra_days": 10 }
  ]
}
```

**Example response (abridged):**
```json
{
  "before": { "lines_at_risk": 2, "revenue_at_risk": 1850000, "days_to_impact": 9 },
  "after":  { "lines_at_risk": 0, "revenue_at_risk": 0, "days_to_impact": null },
  "affected_path": ["GreenLatex", "RubberCore", "TyreWorks", "Line-A"]
}
```

---

## 7. Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.11+, FastAPI | Fast to build, strong typing, auto-generated docs |
| Graph | NetworkX | Simple, rich algorithms, enough for prototype scale |
| AI extraction | LLM API with JSON/structured output | Handles messy, varied documents |
| Validation | Pydantic | Enforces extraction schema |
| Entity matching | RapidFuzz | Lightweight fuzzy matching |
| Storage | SQLite (SQLAlchemy) | Zero setup |
| Doc parsing | pdfplumber, pandas | PDFs and CSVs |
| Frontend | React + Cytoscape.js (or plain HTML + vis-network) | Interactive graph rendering |
| Charts | Recharts / Chart.js | Risk visualisations |
| Testing | pytest | Unit tests for graph, scoring, simulation |

**Scale-up path:** NetworkX → Neo4j; SQLite → PostgreSQL; synchronous extraction → task queue (Celery/RQ).

---

## 8. Project Structure

```
tierlens-ai/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── requirements.txt
├── .env.example
├── data/
│   ├── sample_docs/          # synthetic POs, supplier records
│   ├── suppliers.csv
│   └── events.json           # simulated disruptions
├── backend/
│   ├── main.py               # FastAPI app entry
│   ├── config.py             # weights, thresholds, settings
│   ├── models/               # Pydantic + SQLAlchemy models
│   ├── ingestion/            # loaders, chunking
│   ├── extraction/           # LLM prompts, schemas, entity resolution
│   ├── graph/                # graph builder, tiering, dependency analyzer
│   ├── risk/                 # scoring, alerts
│   ├── simulation/           # what-if engine, mitigations
│   ├── recommender/          # alternative suppliers
│   └── api/                  # route modules
├── frontend/
│   ├── src/
│   │   ├── components/       # GraphView, AlertsPanel, ImpactView, WhatIfLab
│   │   └── services/api.js
│   └── package.json
└── tests/
    ├── test_graph.py
    ├── test_risk.py
    └── test_simulation.py
```

---

## 9. Explainability and Trust

- **Evidence-first:** every edge stores `source_doc` and `snippet`, and the UI shows them on click.
- **Confidence scores** are visible. Low-confidence edges are drawn dashed and queued for review.
- **Score breakdown** accompanies every risk number.
- **LLM boundaries:** the LLM never invents risk numbers. It extracts text into structure and phrases the already computed results.

---

## 10. Error Handling and Quality

| Concern | Approach |
|---|---|
| LLM returns invalid JSON | Schema validation, retry once, then flag the chunk |
| Hallucinated relationship | Require a supporting snippet that exists in the source text |
| Duplicate suppliers | Entity resolution plus alias table |
| Cycles or disconnected nodes in graph | Detect and report, and cap traversal depth |
| Missing lead time or inventory | Use configurable defaults and mark the result as "estimated" |

**Testing focus:** planted hidden dependencies are found; a Tier 3 failure reaches the correct line; mitigations reduce exposure; extraction recall on the sample set.

---

## 11. Security and Privacy (Prototype Level)

- Synthetic data only, with no real customer information.
- API keys in `.env`, never committed.
- Input file type and size limits on upload.
- Future: authentication, role-based access, audit log and per-tenant data isolation.

---

## 12. Deployment

**Prototype:** run locally.
```
pip install -r requirements.txt
uvicorn backend.main:app --reload     # API on :8000
cd frontend && npm install && npm run dev   # UI on :5173
```

**Later:** Docker Compose (API, UI, database) and a cloud deployment with a managed Postgres and graph DB.

---

## 13. Technical Decisions Log

| Decision | Rationale | Revisit when |
|---|---|---|
| NetworkX over Neo4j | No setup, enough for ~100 nodes | Graph exceeds tens of thousands of nodes |
| LLM only for extraction and explanation | Keeps numbers deterministic and testable | Need learned risk prediction |
| Rule-based, weighted risk score | Transparent and easy to tune | Enough historical data for ML |
| SQLite | Zero-config for demo | Multi-user or production use |
| Human review queue | Controls hallucination risk | Extraction accuracy proves high |

---

## 14. Build Order (Suggested)

1. Sample data (documents, suppliers, events)
2. Extraction service and schemas
3. Graph builder and tiering
4. Dependency analyzer
5. Risk engine and alerts
6. Simulation engine and recommender
7. API layer
8. Frontend (graph, alerts, impact, what-if)
9. Tests, polish and demo script
