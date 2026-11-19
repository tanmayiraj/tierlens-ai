# TierLens AI: Database Schema

**Version:** 0.1 (Prototype)
**Companions:** `PRD.md`, `ARCHITECTURE.md`
**Database:** SQLite (via SQLAlchemy), with a path to PostgreSQL
**Graph:** Built in memory (NetworkX) from these tables on startup and after each approved extraction

---

## 1. Design Principles

| Principle | How it shows up in the schema |
|---|---|
| **Evidence-first** | Every relationship links to an `evidence` row, which links to a `documents` row |
| **Explainable scoring** | Alerts store the full factor breakdown as JSON |
| **Resolve, don't lose** | Original supplier names are kept in an alias table after entity resolution |
| **Review before trust** | Extracted facts carry a `status` (pending / approved / rejected) |
| **Simulations are separate** | Scenario runs are stored apart from real events so they never pollute live data |
| **Portable** | Plain types and standard constraints, so the schema moves to PostgreSQL unchanged |

---

## 2. Entity Relationship Overview

```
documents ──< evidence >── relationships >── suppliers (supplier side)
                               │   └──────── suppliers (buyer side)
                               └──────────── materials

suppliers ──< supplier_aliases
suppliers ──< supplier_materials >── materials
suppliers ──< events ──< alerts ──< alert_affected_nodes

production_lines ──< line_requirements >── materials
production_lines >── plants
products ──< production_lines

scenarios ──< scenario_results
```

`<` marks one-to-many. `>──<` marks many-to-many through a link table.

---

## 3. Tables

### 3.1 `documents`
Source files uploaded or loaded as samples.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | |
| filename | TEXT | NOT NULL | e.g. `PO_1042.pdf` |
| doc_type | TEXT | NOT NULL | `purchase_order`, `supplier_record`, `contract`, `invoice`, `procurement_note` |
| file_path | TEXT | NOT NULL | Location of the raw file |
| raw_text | TEXT | | Extracted full text |
| page_count | INTEGER | | |
| extraction_status | TEXT | NOT NULL, default `pending` | `pending`, `processing`, `done`, `failed` |
| uploaded_at | DATETIME | NOT NULL, default now | |

### 3.2 `suppliers`
Canonical (resolved) supplier records, including the manufacturer's own plants as buyers.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL, UNIQUE | Canonical name |
| entity_type | TEXT | NOT NULL, default `supplier` | `manufacturer`, `supplier` |
| country | TEXT | | |
| region | TEXT | | Used for regional risk |
| latitude | REAL | | Optional, for map view |
| longitude | REAL | | Optional, for map view |
| capacity_per_month | REAL | | In the supplier's primary unit |
| base_risk | REAL | default 0, CHECK 0 to 100 | Static baseline risk |
| is_active | BOOLEAN | NOT NULL, default 1 | |
| created_at | DATETIME | NOT NULL, default now | |

### 3.3 `supplier_aliases`
Alternate spellings found in documents, mapped to the canonical supplier.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| supplier_id | INTEGER | FK → suppliers.id, NOT NULL, ON DELETE CASCADE | |
| alias | TEXT | NOT NULL | e.g. "ABC Rubber Pvt Ltd" |
| match_score | REAL | | Fuzzy match score, 0 to 1 |
| resolved_by | TEXT | | `rule`, `fuzzy`, `llm`, `manual` |

Unique constraint: (`supplier_id`, `alias`).

### 3.4 `materials`
Raw materials, parts and assemblies.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL, UNIQUE | e.g. `Natural Latex` |
| material_type | TEXT | NOT NULL | `raw`, `part`, `assembly` |
| unit | TEXT | | `MT`, `kg`, `units` |
| category | TEXT | | e.g. `rubber`, `steel`, `electronics` |

### 3.5 `supplier_materials`
What each supplier is capable of providing. Used by the alternative-supplier recommender.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| supplier_id | INTEGER | FK → suppliers.id, NOT NULL | |
| material_id | INTEGER | FK → materials.id, NOT NULL | |
| capacity_per_month | REAL | | |
| typical_lead_time_days | INTEGER | | |
| is_qualified | BOOLEAN | NOT NULL, default 0 | Approved by the manufacturer's quality team |

Primary key: (`supplier_id`, `material_id`).

### 3.6 `evidence`
The exact snippet in a document that supports an extracted fact.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| document_id | INTEGER | FK → documents.id, NOT NULL, ON DELETE CASCADE | |
| page | INTEGER | | |
| chunk_index | INTEGER | | |
| snippet | TEXT | NOT NULL | Verbatim source text |
| llm_confidence | REAL | CHECK 0 to 1 | |
| extracted_at | DATETIME | NOT NULL, default now | |

### 3.7 `relationships`
The core edge table: "supplier S supplies material M to buyer B."

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| supplier_id | INTEGER | FK → suppliers.id, NOT NULL | Upstream party |
| buyer_id | INTEGER | FK → suppliers.id, NOT NULL | Downstream party |
| material_id | INTEGER | FK → materials.id, NOT NULL | |
| tier | INTEGER | CHECK ≥ 1 | Computed relative to the manufacturer |
| lead_time_days | INTEGER | | |
| share_pct | REAL | CHECK 0 to 100 | Share of buyer's demand for this material |
| inventory_days | INTEGER | default 0 | Buffer stock held by the buyer |
| quantity_per_month | REAL | | |
| confidence | REAL | CHECK 0 to 1 | |
| status | TEXT | NOT NULL, default `pending` | `pending`, `approved`, `rejected` |
| evidence_id | INTEGER | FK → evidence.id | Primary supporting evidence |
| reviewed_by | TEXT | | |
| reviewed_at | DATETIME | | |
| created_at | DATETIME | NOT NULL, default now | |

Constraints:
- CHECK (`supplier_id` <> `buyer_id`)
- UNIQUE (`supplier_id`, `buyer_id`, `material_id`)

### 3.8 `relationship_evidence`
Lets one relationship be backed by several documents.

| Column | Type | Constraints |
|---|---|---|
| relationship_id | INTEGER | FK → relationships.id, ON DELETE CASCADE |
| evidence_id | INTEGER | FK → evidence.id, ON DELETE CASCADE |

Primary key: (`relationship_id`, `evidence_id`).

### 3.9 `plants`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| manufacturer_id | INTEGER | FK → suppliers.id, NOT NULL | The manufacturer entity |
| name | TEXT | NOT NULL | e.g. `Pune Assembly Plant` |
| location | TEXT | | |

### 3.10 `products`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL, UNIQUE | e.g. `Sedan X` |
| unit_revenue | REAL | | Revenue per unit |

### 3.11 `production_lines`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| plant_id | INTEGER | FK → plants.id, NOT NULL | |
| product_id | INTEGER | FK → products.id, NOT NULL | |
| name | TEXT | NOT NULL | e.g. `Line A` |
| units_per_day | REAL | NOT NULL | |
| daily_revenue | REAL | | Derived or entered, used for exposure |

### 3.12 `line_requirements`
Which materials or components each line needs, and from which Tier 1 buyer relationship they arrive.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| line_id | INTEGER | FK → production_lines.id, ON DELETE CASCADE | |
| material_id | INTEGER | FK → materials.id | |
| qty_per_day | REAL | NOT NULL | |
| criticality | TEXT | NOT NULL, default `high` | `high`, `medium`, `low` |
| safety_stock_days | INTEGER | default 0 | Stock held at the plant |

Primary key: (`line_id`, `material_id`).

### 3.13 `events`
Real or simulated disruption events.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| supplier_id | INTEGER | FK → suppliers.id, NOT NULL | |
| event_type | TEXT | NOT NULL | `shutdown`, `delay`, `shortage`, `transport`, `natural_disaster`, `quality` |
| severity | INTEGER | NOT NULL, CHECK 1 to 5 | |
| start_date | DATE | NOT NULL | |
| expected_duration_days | INTEGER | | |
| description | TEXT | | |
| source | TEXT | | News link, feed name or `simulated` |
| is_simulated | BOOLEAN | NOT NULL, default 1 | |
| created_at | DATETIME | NOT NULL, default now | |

### 3.14 `alerts`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| event_id | INTEGER | FK → events.id, NOT NULL, ON DELETE CASCADE | |
| severity_label | TEXT | NOT NULL | `low`, `medium`, `high`, `critical` |
| risk_score | REAL | NOT NULL, CHECK 0 to 100 | |
| score_breakdown | JSON | NOT NULL | Factor-by-factor contribution |
| days_to_impact | INTEGER | | Null if absorbed by buffers |
| revenue_at_risk | REAL | | |
| explanation | TEXT | | LLM-phrased from computed facts |
| status | TEXT | NOT NULL, default `open` | `open`, `acknowledged`, `resolved` |
| created_at | DATETIME | NOT NULL, default now | |

**`score_breakdown` example:**
```json
{
  "event_severity": 24,
  "criticality": 22,
  "single_source_exposure": 20,
  "buffer_gap": 12,
  "regional_risk": 5,
  "total": 83
}
```

### 3.15 `alert_affected_nodes`
Everything downstream of the disruption.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| alert_id | INTEGER | FK → alerts.id, ON DELETE CASCADE | |
| node_type | TEXT | NOT NULL | `supplier`, `material`, `line`, `product` |
| node_id | INTEGER | NOT NULL | ID in the matching table |
| path_depth | INTEGER | | Hops from the disrupted supplier |
| days_to_impact | INTEGER | | |

### 3.16 `scenarios`
What-if runs, stored separately from real events.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| name | TEXT | NOT NULL | |
| failed_supplier_ids | JSON | NOT NULL | List of supplier IDs |
| duration_days | INTEGER | NOT NULL | |
| mitigations | JSON | | List of mitigation objects |
| created_at | DATETIME | NOT NULL, default now | |

### 3.17 `scenario_results`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK | |
| scenario_id | INTEGER | FK → scenarios.id, ON DELETE CASCADE | |
| variant | TEXT | NOT NULL | `before_mitigation`, `after_mitigation` |
| lines_at_risk | INTEGER | | |
| revenue_at_risk | REAL | | |
| days_to_impact | INTEGER | | |
| affected_path | JSON | | Ordered node list |
| result_detail | JSON | | Full output for the UI |

### 3.18 `review_queue` (optional view)
Pending low-confidence extractions. Can be a view instead of a table:

```sql
CREATE VIEW review_queue AS
SELECT r.id, s.name AS supplier, b.name AS buyer, m.name AS material,
       r.confidence, e.snippet, d.filename
FROM relationships r
JOIN suppliers s ON s.id = r.supplier_id
JOIN suppliers b ON b.id = r.buyer_id
JOIN materials m ON m.id = r.material_id
LEFT JOIN evidence e ON e.id = r.evidence_id
LEFT JOIN documents d ON d.id = e.document_id
WHERE r.status = 'pending'
ORDER BY r.confidence ASC;
```

---

## 4. SQL (SQLite DDL)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  raw_text TEXT,
  page_count INTEGER,
  extraction_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (extraction_status IN ('pending','processing','done','failed')),
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suppliers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  entity_type TEXT NOT NULL DEFAULT 'supplier'
    CHECK (entity_type IN ('manufacturer','supplier')),
  country TEXT,
  region TEXT,
  latitude REAL,
  longitude REAL,
  capacity_per_month REAL,
  base_risk REAL DEFAULT 0 CHECK (base_risk BETWEEN 0 AND 100),
  is_active BOOLEAN NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE supplier_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  match_score REAL,
  resolved_by TEXT,
  UNIQUE (supplier_id, alias)
);

CREATE TABLE materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  material_type TEXT NOT NULL CHECK (material_type IN ('raw','part','assembly')),
  unit TEXT,
  category TEXT
);

CREATE TABLE supplier_materials (
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  material_id INTEGER NOT NULL REFERENCES materials(id),
  capacity_per_month REAL,
  typical_lead_time_days INTEGER,
  is_qualified BOOLEAN NOT NULL DEFAULT 0,
  PRIMARY KEY (supplier_id, material_id)
);

CREATE TABLE evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page INTEGER,
  chunk_index INTEGER,
  snippet TEXT NOT NULL,
  llm_confidence REAL CHECK (llm_confidence BETWEEN 0 AND 1),
  extracted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE relationships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  buyer_id INTEGER NOT NULL REFERENCES suppliers(id),
  material_id INTEGER NOT NULL REFERENCES materials(id),
  tier INTEGER CHECK (tier >= 1),
  lead_time_days INTEGER,
  share_pct REAL CHECK (share_pct BETWEEN 0 AND 100),
  inventory_days INTEGER DEFAULT 0,
  quantity_per_month REAL,
  confidence REAL CHECK (confidence BETWEEN 0 AND 1),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','rejected')),
  evidence_id INTEGER REFERENCES evidence(id),
  reviewed_by TEXT,
  reviewed_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (supplier_id <> buyer_id),
  UNIQUE (supplier_id, buyer_id, material_id)
);

CREATE TABLE relationship_evidence (
  relationship_id INTEGER NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
  evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
  PRIMARY KEY (relationship_id, evidence_id)
);

CREATE TABLE plants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  manufacturer_id INTEGER NOT NULL REFERENCES suppliers(id),
  name TEXT NOT NULL,
  location TEXT
);

CREATE TABLE products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  unit_revenue REAL
);

CREATE TABLE production_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER NOT NULL REFERENCES plants(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  name TEXT NOT NULL,
  units_per_day REAL NOT NULL,
  daily_revenue REAL
);

CREATE TABLE line_requirements (
  line_id INTEGER NOT NULL REFERENCES production_lines(id) ON DELETE CASCADE,
  material_id INTEGER NOT NULL REFERENCES materials(id),
  qty_per_day REAL NOT NULL,
  criticality TEXT NOT NULL DEFAULT 'high'
    CHECK (criticality IN ('high','medium','low')),
  safety_stock_days INTEGER DEFAULT 0,
  PRIMARY KEY (line_id, material_id)
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  event_type TEXT NOT NULL
    CHECK (event_type IN ('shutdown','delay','shortage','transport','natural_disaster','quality')),
  severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
  start_date DATE NOT NULL,
  expected_duration_days INTEGER,
  description TEXT,
  source TEXT,
  is_simulated BOOLEAN NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  severity_label TEXT NOT NULL CHECK (severity_label IN ('low','medium','high','critical')),
  risk_score REAL NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  score_breakdown JSON NOT NULL,
  days_to_impact INTEGER,
  revenue_at_risk REAL,
  explanation TEXT,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','acknowledged','resolved')),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alert_affected_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
  node_type TEXT NOT NULL CHECK (node_type IN ('supplier','material','line','product')),
  node_id INTEGER NOT NULL,
  path_depth INTEGER,
  days_to_impact INTEGER
);

CREATE TABLE scenarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  failed_supplier_ids JSON NOT NULL,
  duration_days INTEGER NOT NULL,
  mitigations JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scenario_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  variant TEXT NOT NULL CHECK (variant IN ('before_mitigation','after_mitigation')),
  lines_at_risk INTEGER,
  revenue_at_risk REAL,
  days_to_impact INTEGER,
  affected_path JSON,
  result_detail JSON
);
```

---

## 5. Indexes

```sql
CREATE INDEX idx_rel_supplier   ON relationships(supplier_id);
CREATE INDEX idx_rel_buyer      ON relationships(buyer_id);
CREATE INDEX idx_rel_material   ON relationships(material_id);
CREATE INDEX idx_rel_status     ON relationships(status);
CREATE INDEX idx_evidence_doc   ON evidence(document_id);
CREATE INDEX idx_alias_alias    ON supplier_aliases(alias);
CREATE INDEX idx_events_supplier ON events(supplier_id);
CREATE INDEX idx_alerts_event   ON alerts(event_id);
CREATE INDEX idx_alerts_status  ON alerts(status, risk_score DESC);
CREATE INDEX idx_affected_alert ON alert_affected_nodes(alert_id);
CREATE INDEX idx_supmat_material ON supplier_materials(material_id);
```

---

## 6. Tier Computation

`relationships.tier` is not entered by hand. It is derived by the graph service:

1. Start at the manufacturer node (`entity_type = 'manufacturer'`).
2. Suppliers with an edge directly to the manufacturer are **Tier 1**.
3. Suppliers with an edge to a Tier 1 supplier are **Tier 2**, and so on (shortest-path distance).
4. A supplier reachable by several paths takes the **shortest** tier, but all paths are kept in the graph for dependency analysis.
5. Results are written back to `relationships.tier` for fast filtering.

---

## 7. Useful Queries

**All suppliers of a given material, with tier and share:**
```sql
SELECT s.name, r.tier, r.share_pct, r.lead_time_days
FROM relationships r
JOIN suppliers s ON s.id = r.supplier_id
JOIN materials m ON m.id = r.material_id
WHERE m.name = 'Natural Latex' AND r.status = 'approved';
```

**Single-source materials (no alternative supplier):**
```sql
SELECT m.name, COUNT(DISTINCT r.supplier_id) AS supplier_count
FROM relationships r
JOIN materials m ON m.id = r.material_id
WHERE r.status = 'approved'
GROUP BY m.id
HAVING supplier_count = 1;
```

**Hidden shared upstream suppliers (feed 2 or more buyers):**
```sql
SELECT s.name, COUNT(DISTINCT r.buyer_id) AS buyers_fed
FROM relationships r
JOIN suppliers s ON s.id = r.supplier_id
WHERE r.tier >= 2 AND r.status = 'approved'
GROUP BY r.supplier_id
HAVING buyers_fed >= 2
ORDER BY buyers_fed DESC;
```

**Qualified alternatives for a material, excluding the failed supplier:**
```sql
SELECT s.name, sm.capacity_per_month, sm.typical_lead_time_days, s.base_risk
FROM supplier_materials sm
JOIN suppliers s ON s.id = sm.supplier_id
WHERE sm.material_id = :material_id
  AND sm.supplier_id <> :failed_supplier_id
  AND sm.is_qualified = 1
ORDER BY s.base_risk ASC, sm.typical_lead_time_days ASC;
```

**Evidence behind one relationship:**
```sql
SELECT d.filename, e.page, e.snippet, e.llm_confidence
FROM relationship_evidence re
JOIN evidence e ON e.id = re.evidence_id
JOIN documents d ON d.id = e.document_id
WHERE re.relationship_id = :relationship_id;
```

**Open alerts ranked by severity:**
```sql
SELECT a.id, s.name AS supplier, ev.event_type, a.risk_score,
       a.days_to_impact, a.revenue_at_risk
FROM alerts a
JOIN events ev ON ev.id = a.event_id
JOIN suppliers s ON s.id = ev.supplier_id
WHERE a.status = 'open'
ORDER BY a.risk_score DESC;
```

---

## 8. Mapping to the In-Memory Graph

| Database | NetworkX |
|---|---|
| `suppliers` row | Node (`type='Supplier'`) with `name`, `tier`, `region`, `risk_score` |
| `materials` row | Node (`type='Material'`) |
| `production_lines` row | Node (`type='ProductionLine'`) |
| `relationships` row (approved) | Directed edge supplier → buyer with `material`, `lead_time_days`, `share_pct`, `inventory_days`, `confidence`, `evidence_id` |
| `line_requirements` row | Edge material/Tier 1 supplier → production line |

Only `status = 'approved'` relationships are loaded. Pending ones can optionally be drawn as dashed edges in the UI.

---

## 9. Sample Seed Data (Car Manufacturer Example)

| Tier | Supplier | Supplies | To |
|---|---|---|---|
| Manufacturer | AutoMotive Corp | | |
| 1 | TyreWorks Ltd | Tyres | AutoMotive Corp |
| 2 | RubberCore Industries | Processed Rubber | TyreWorks Ltd |
| 2 | RubberCore Industries | Processed Rubber | GripSeal Components (also Tier 1) |
| 3 | GreenLatex Pvt Ltd | Natural Latex | RubberCore Industries |
| 3 | PetroChem Asia | Carbon Black | RubberCore Industries |

Here `RubberCore Industries` and `GreenLatex Pvt Ltd` are hidden dependencies: a Tier 3 failure at GreenLatex reaches both TyreWorks and GripSeal, and therefore the production lines that use tyres and seals.

---

## 10. Data Integrity and Lifecycle

| Concern | Rule |
|---|---|
| Orphaned evidence | Deleting a document cascades to its evidence and link rows |
| Rejected extractions | Kept with `status='rejected'` so they are not re-suggested |
| Simulations vs real events | `events.is_simulated` separates them. Scenario runs live in their own tables |
| Resolved duplicates | The merged supplier's old name becomes a row in `supplier_aliases` |
| Self-supply | Blocked by `CHECK (supplier_id <> buyer_id)` |
| Cycles in supply chain | Allowed in the table, but detected and reported by the graph service |
| Missing values | `lead_time_days` and `inventory_days` may be null. The risk engine applies configured defaults and marks the result as estimated |

---

## 11. Migration Path

| Stage | Change |
|---|---|
| Prototype | SQLite file `tierlens.db`, tables created from SQLAlchemy models or the DDL above |
| Growth | PostgreSQL. Change `JSON` to `JSONB`, add proper enums, add indexes on JSONB fields if needed |
| Graph scale | Mirror `suppliers` and `relationships` into Neo4j for deep traversal and graph analytics |
| Multi-tenant | Add `tenant_id` to every table and enforce row-level security |
| Migrations | Use Alembic to version all schema changes |
