# TierLens AI: Product Requirements Document

**Product:** TierLens AI, Multi-Level Supplier Risk Intelligence
**Version:** 0.1 (Prototype / MVP)
**Tagline:** An early-warning system that shows manufacturers hidden supplier risks before production is affected.

---

## 1. Overview

Manufacturers rely on many suppliers for raw materials and components, but they usually only see their direct (Tier 1) suppliers. A disruption at a hidden upstream supplier (Tier 2 or Tier 3), such as a factory shutdown, material shortage or transport delay, can cascade through the chain and stop production.

TierLens AI reads procurement documents, extracts supplier relationships using AI, builds an interactive multi-tier supplier network, and shows exactly which suppliers, components and production lines are exposed when something goes wrong.

**Running example:** A car manufacturer buys tyres (Tier 1) from a tyre maker, who buys rubber (Tier 2) from a rubber processor, who buys raw material (Tier 3) from a plantation or chemical supplier. If the Tier 3 supplier shuts down, tyre output falls and car production eventually halts. The manufacturer would not see this coming without multi-tier visibility.

---

## 2. Problem Statement

| Problem | Impact |
|---|---|
| Visibility stops at Tier 1 | Hidden dependencies go unnoticed |
| Supplier data is scattered across POs, contracts, invoices, spreadsheets and emails | Mapping the network by hand is slow and error-prone |
| Disruptions are discovered after they hit | Production stoppages, expedited-freight costs, lost revenue |
| No easy way to ask "what if supplier X fails?" | Slow, reactive decisions and weak contingency planning |

---

## 3. Target Users

| Persona | Needs |
|---|---|
| **Supply Chain / Risk Manager** (primary) | See hidden dependencies, get early alerts, justify decisions with evidence |
| **Procurement Manager** | Find and compare alternative suppliers quickly |
| **Production / Plant Planner** | Know which lines and components are at risk and when |
| **Executive / Operations Head** | High-level exposure view and estimated financial impact |

---

## 4. Goals and Non-Goals

### Goals (prototype)
1. Extract supplier names, materials and relationships from sample business documents.
2. Build and display an interactive Tier 1 to Tier 3 supplier network graph.
3. Identify hidden dependencies (shared upstream suppliers, single points of failure).
4. Detect simulated disruption events and flag affected suppliers, components and production lines.
5. Provide evidence-based alerts that link back to the source document.
6. Support what-if simulations and suggest alternative suppliers.

### Non-Goals (for now)
- Live ERP/SAP integration
- Real-time scraping of global news or satellite data
- Automated purchasing or contract actions
- Supplier-facing portal
- Production-grade security, multi-tenancy and user management

---

## 5. Solution Summary

TierLens AI has five capabilities:

1. **Document Intelligence:** AI extracts entities (suppliers, materials, components, plants) and relationships ("A supplies B with material M") from POs, supplier records and procurement documents.
2. **Supplier Network Map:** Relationships are organised into a multi-tier graph. Users can explore it interactively.
3. **Hidden Dependency Detection:** Graph analysis surfaces shared Tier 2/3 suppliers, single-source materials and concentration risk.
4. **Disruption Impact Analysis:** When a disruption is logged or simulated, the system traces downstream to affected suppliers, components, production lines and finished products.
5. **Response Planning:** Alternative supplier suggestions, mitigation options and what-if scenarios.

---

## 6. Functional Requirements

### 6.1 Document Ingestion and Extraction
| ID | Requirement | Priority |
|---|---|---|
| F1 | Upload or load sample documents (PDF, TXT, CSV) | Must |
| F2 | Extract supplier names, materials/components, quantities, locations and relationships | Must |
| F3 | Assign each extracted fact a confidence score and a source reference (document, snippet) | Must |
| F4 | Normalise duplicate supplier names (e.g., "ABC Rubber Pvt Ltd" and "ABC Rubber") | Should |
| F5 | Allow user to review and correct extracted relationships | Should |

### 6.2 Supplier Network Graph
| ID | Requirement | Priority |
|---|---|---|
| F6 | Interactive graph with nodes (supplier, component, plant/line) and edges (supplies) | Must |
| F7 | Colour/shape by tier and by risk level | Must |
| F8 | Click a node to see details: location, materials supplied, customers, risk score, evidence | Must |
| F9 | Filter by tier, material, region and risk level | Should |
| F10 | Highlight hidden dependencies (e.g., one Tier 3 supplier feeding multiple Tier 2 suppliers) | Must |

### 6.3 Risk Detection and Alerts
| ID | Requirement | Priority |
|---|---|---|
| F11 | Ingest simulated disruption events (shutdown, delay, shortage, transport issue) | Must |
| F12 | Compute a risk score per supplier based on event severity, tier depth, concentration and alternatives available | Must |
| F13 | Generate alerts with a plain-language explanation and linked evidence | Must |
| F14 | Rank alerts by severity and estimated production impact | Should |

### 6.4 Impact Analysis
| ID | Requirement | Priority |
|---|---|---|
| F15 | Trace a disruption downstream to affected suppliers, components, production lines and products | Must |
| F16 | Show estimated time-to-impact using lead times and inventory buffers | Should |
| F17 | Show estimated financial exposure (revenue at risk per day) | Should |

### 6.5 What-If Simulation
| ID | Requirement | Priority |
|---|---|---|
| F18 | Let users pick a supplier (or region/material) and simulate failure for N days | Must |
| F19 | Show before/after exposure comparison | Must |
| F20 | Let users toggle mitigation levers (switch to alternate supplier, add safety stock, reroute) and see the effect | Should |

### 6.6 Alternative Supplier Suggestions
| ID | Requirement | Priority |
|---|---|---|
| F21 | Suggest alternatives from the supplier database matching the same material/capability | Must |
| F22 | Rank by lead time, capacity, region risk and existing relationship | Should |
| F23 | Explain why each alternative is suggested | Should |

---

## 7. Key User Flows

**Flow 1: Build the map**
1. User uploads sample documents.
2. System extracts suppliers and relationships.
3. User reviews the extracted graph and confirms.

**Flow 2: Discover hidden risk**
1. User opens the network view.
2. System highlights single points of failure and shared upstream suppliers.
3. User clicks a node and sees the evidence behind each link.

**Flow 3: Respond to a disruption**
1. A disruption event appears (e.g., "Tier 3 supplier shut down").
2. System raises an alert with affected suppliers, components and lines.
3. User opens impact analysis and sees time-to-impact.
4. User reviews suggested alternatives.

**Flow 4: What-if planning**
1. User selects a supplier and a disruption type and duration.
2. System runs the simulation and shows downstream impact.
3. User toggles mitigations and compares outcomes.

---

## 8. System Architecture (Prototype)

```
 Documents (PO, supplier records)
            |
            v
   [Extraction Service]  -- LLM-based entity + relationship extraction
            |
            v
   [Knowledge Graph]     -- NetworkX (nodes: suppliers, materials, components, lines)
            |
   +--------+---------+------------------+
   |                  |                  |
   v                  v                  v
[Dependency      [Risk Engine]     [Simulation
 Analyzer]        scores + alerts    Engine]
   |                  |                  |
   +--------+---------+------------------+
            |
            v
      [REST API: FastAPI]
            |
            v
   [Web UI: graph, alerts, what-if]
```

**Suggested stack:** Python, FastAPI, NetworkX, an LLM API for extraction, and a React or plain-HTML frontend with a graph library (e.g., vis-network or Cytoscape.js).

---

## 9. Data Model (simplified)

| Entity | Key fields |
|---|---|
| **Supplier** | id, name, tier, location, capacity, risk_score |
| **Material / Component** | id, name, type (raw / part / assembly) |
| **Relationship** | from_supplier, to_supplier, material, lead_time_days, share_of_supply_%, source_doc, confidence |
| **Production Line** | id, plant, product, components_required |
| **Disruption Event** | id, supplier_id, type, severity, start_date, expected_duration, source |
| **Alert** | id, event_id, affected_nodes, severity, explanation, evidence |

---

## 10. Risk Scoring Logic (initial approach)

A transparent, explainable score from 0 to 100:

```
Risk = w1 * Event Severity
     + w2 * Supplier Criticality      (how many downstream nodes depend on it)
     + w3 * Single-Source Exposure    (no alternative for the material)
     + w4 * Inventory Buffer Gap      (days of stock vs. expected disruption length)
     + w5 * Regional Risk
```

Every alert must show which factors drove the score so users can trust it.

---

## 11. Success Metrics

### Prototype / demo
- Extracts at least 90% of planted supplier relationships from the sample documents.
- Correctly identifies all planted hidden dependencies.
- Propagates a simulated Tier 3 disruption to the correct Tier 1 supplier, component and production line.
- Every alert links to at least one source document.
- Full demo flow runs end to end in under 5 minutes.

### Product (future)
- Reduction in unplanned production stoppages
- Time taken to detect a hidden-tier risk
- Percentage of the supply base mapped beyond Tier 1
- Time to decide on a response after an alert

---

## 12. Prototype Scope

**In scope**
- Synthetic car-manufacturer dataset: tyres, rubber, raw materials plus a few other component chains
- 15 to 30 suppliers across three tiers, with deliberate hidden dependencies
- 8 to 12 sample documents (purchase orders, supplier records, procurement notes)
- Graph view, alerts panel, impact view and what-if simulator

**Out of scope**
- Real customer data, authentication, production deployment

---

## 13. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM extraction errors or hallucinated relationships | Confidence scores, source snippets, human review step |
| Inconsistent supplier names across documents | Entity resolution and fuzzy matching |
| Sparse data beyond Tier 1 in real life | Allow manual entry, supplier questionnaires and third-party data later |
| Users distrust black-box scores | Explainable factor breakdown on every alert |
| Over-scoping for the demo | Fixed sample dataset and a scripted scenario |

---

## 14. Roadmap

| Phase | Focus |
|---|---|
| **Phase 1 (Prototype)** | Extraction, graph, hidden dependencies, simulated disruptions, what-if |
| **Phase 2** | Live external signals (news, weather, port and geopolitical feeds), better entity resolution |
| **Phase 3** | ERP/procurement integrations, deeper tiers (Tier 4+), financial impact modelling |
| **Phase 4** | Automated mitigation playbooks, supplier collaboration, multi-plant optimisation |

---

## 15. Open Questions

1. Which industry example should be the primary demo (automotive, electronics, other)?
2. Should the UI be a full web app (React) or a faster Streamlit dashboard?
3. Which LLM and extraction approach will be used for documents?
4. Is financial impact in scope for the demo, or only operational impact?
5. How many what-if levers should the simulator expose?

---

## 16. One-Line Summary

TierLens AI maps the supplier network beyond Tier 1, finds hidden dependencies, and shows how one upstream disruption can ripple through to production, so companies can act before it happens.
