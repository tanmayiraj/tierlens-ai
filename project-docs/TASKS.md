# TASKS.md
# TierLens AI – Development Task Plan

## 1. Purpose

This file defines what should be implemented first, what depends on earlier work, and how to verify that each stage is complete.

The goal is to build a working TierLens AI prototype in small, testable steps. The first milestone is a reliable supplier network using synthetic sample data. Document extraction, risk analysis, impact analysis and simulation should be added on top of that foundation.

Follow these project documents while implementing tasks:

- `PRD.md` – product scope and requirements.
- `ARCHITECTURE.md` – system architecture and component responsibilities.
- `DATABASE_SCHEMA.md` – database tables and relationships.
- `API_SPEC.md` – API contracts.
- `DESIGN_SYSTEM.md` – frontend design and interaction rules.
- `AGENTS.md` – instructions for AI coding agents.

If the implementation and documentation disagree, do not silently choose one. Identify the mismatch and resolve it before making changes that could break compatibility.

---

## 2. Implementation Rules

1. Inspect the existing repository and documentation before starting a task.
2. Complete tasks in dependency order unless a dependency is explicitly marked optional.
3. Use the agreed stack: React, FastAPI, SQLite, NetworkX and the libraries documented in `DESIGN_SYSTEM.md`.
4. Start with synthetic sample data. Do not make external data integrations a prerequisite for the prototype.
5. Keep sample data clearly labelled as synthetic.
6. Do not invent supplier relationships, risk evidence, inventory, capacity or production figures.
7. Keep extracted information reviewable before treating it as confirmed supplier data.
8. Separate confirmed information, detected risk, prediction and hypothetical simulation results.
9. Do not change API contracts or database structures without checking their dependent components and updating the relevant documentation.
10. A task is complete only when its acceptance criteria have been checked. Do not claim tests passed unless they were run.

---

## 3. Build Order at a Glance

| Order | Phase | Main outcome | Priority |
|---:|---|---|---|
| 1 | Repository and environment setup | Frontend and backend run locally | P0 |
| 2 | Database and sample data | Consistent automotive supplier dataset | P0 |
| 3 | Supplier management API | Suppliers and relationships can be managed | P0 |
| 4 | Supplier graph engine | Multi-tier network and traversal work | P0 |
| 5 | Frontend foundation | Navigation and dashboard shell are ready | P0 |
| 6 | Supplier directory and network UI | Users can inspect the supplier ecosystem | P0 |
| 7 | Risk engine | Rules-based risks can be identified and explained | P1 |
| 8 | Impact analysis | Downstream effects can be traced | P1 |
| 9 | Document intelligence | Documents can be uploaded, extracted and reviewed | P1 |
| 10 | Scenario simulator | Users can test hypothetical disruptions | P1 |
| 11 | Reports and final integration | Results can be presented and exported | P2 |
| 12 | Quality, security and demo readiness | Prototype is tested and demonstrable | P0 |

P0 tasks form the minimum working prototype. P1 tasks add the main intelligence workflows. P2 tasks improve presentation and delivery.

---

# 4. Detailed Tasks

## Phase 1 – Repository and Environment Setup

**Goal:** Establish a working development environment before implementing business features.

### TASK-001: Inspect the repository

- [ ] Inspect the current folder and file structure.
- [ ] Read all existing project documentation.
- [ ] Identify existing frontend and backend code.
- [ ] Identify existing dependencies and configuration.
- [ ] Check the Git working tree before making changes.
- [ ] Record missing files or documentation conflicts.

**Acceptance criteria**

- The existing project structure is understood.
- Existing code and user changes are preserved.
- Any conflicts between project documents are reported before implementation.

### TASK-002: Set up the backend

- [ ] Create or verify the Python virtual environment.
- [ ] Install the dependencies required by the agreed backend stack.
- [ ] Configure the FastAPI application entry point.
- [ ] Configure environment-based settings.
- [ ] Add a health-check endpoint.
- [ ] Configure application logging and error handling.
- [ ] Verify that the API starts locally.

**Acceptance criteria**

- FastAPI starts without errors.
- The health-check endpoint returns a successful response.
- Configuration does not contain hardcoded secrets.

### TASK-003: Set up the frontend

- [ ] Create or verify the React application.
- [ ] Configure Tailwind CSS.
- [ ] Install and configure React Router.
- [ ] Install Lucide React.
- [ ] Install Recharts.
- [ ] Install React Flow.
- [ ] Create the global stylesheet and design tokens.
- [ ] Configure the backend API base URL through environment configuration.

**Acceptance criteria**

- React starts locally.
- The application loads without console errors.
- The frontend can reach the backend health-check endpoint.

---

## Phase 2 – Database and Sample Data

**Goal:** Create a dependable data foundation for all later features.

### TASK-004: Implement the SQLite database

- [ ] Read `DATABASE_SCHEMA.md`.
- [ ] Create the database initialization process.
- [ ] Implement the documented tables and relationships.
- [ ] Enable and verify SQLite foreign-key enforcement.
- [ ] Add the documented indexes.
- [ ] Add a repeatable initialization or migration approach.
- [ ] Verify that initialization does not unintentionally erase existing data.

**Acceptance criteria**

- The database initializes successfully.
- Required tables, keys and indexes exist.
- Foreign-key constraints work.
- Running initialization more than once does not create duplicate seed records or destroy existing data.

### TASK-005: Create synthetic automotive sample data

Use the documented demonstration chain:

```text
Automobile Manufacturer
        ^
        |
Tyre Manufacturer (Tier 1)
        ^
        |
Rubber Manufacturer (Tier 2)
        ^
        |
Raw Material Supplier (Tier 3)
```

- [ ] Create sample organizations and suppliers consistent with the database schema.
- [ ] Add supplier relationships and supplied materials.
- [ ] Add only the supporting component, production, inventory or capacity records defined by the schema.
- [ ] Label the dataset as synthetic demonstration data.
- [ ] Create a repeatable seed script.
- [ ] Verify the expected records and relationships after seeding.

**Acceptance criteria**

- The sample data matches the documented schema.
- The automotive supply chain can be traced through the intended tiers.
- Sample data can be loaded repeatedly without accidental duplication.
- No sample values are presented as real-world facts.

---

## Phase 3 – Supplier Management API

**Goal:** Make supplier and relationship data accessible through the backend.

### TASK-006: Implement supplier endpoints

- [ ] Review the supplier endpoints in `API_SPEC.md`.
- [ ] Implement supplier creation and retrieval.
- [ ] Implement supplier listing.
- [ ] Implement supplier updates and deletion only where defined in the API specification.
- [ ] Add pagination, filtering and sorting where specified.
- [ ] Validate requests using Pydantic schemas.
- [ ] Return the documented response and error formats.

**Acceptance criteria**

- Supplier records can be retrieved from SQLite through the API.
- Invalid requests return appropriate errors.
- API responses match `API_SPEC.md`.
- Database errors do not expose internal details.

### TASK-007: Implement supplier relationship endpoints

- [ ] Implement the documented relationship operations.
- [ ] Validate that both suppliers in a relationship exist.
- [ ] Store the direction of supply consistently.
- [ ] Store material or component details where defined.
- [ ] Prevent invalid self-links and duplicate relationships where required.
- [ ] Handle incomplete or unknown relationships without inventing data.

**Acceptance criteria**

- Valid supplier relationships can be stored and retrieved.
- Supply direction is consistent across database and API.
- Invalid relationships are rejected with understandable errors.

---

## Phase 4 – Supplier Graph Engine

**Goal:** Turn stored supplier relationships into a directed multi-tier network.

### TASK-008: Build the NetworkX graph service

- [ ] Create a dedicated graph service.
- [ ] Load supplier nodes from the database.
- [ ] Load directed supply relationships as graph edges.
- [ ] Preserve supplier IDs and relevant relationship attributes.
- [ ] Handle disconnected nodes and incomplete networks.
- [ ] Avoid adding relationships that are not present in the data.
- [ ] Add tests for graph construction.

**Acceptance criteria**

- The graph reflects the stored supplier relationships.
- Edge direction consistently represents the documented direction of supply.
- Graph nodes can be mapped back to database supplier IDs.
- Missing relationships are not fabricated.

### TASK-009: Implement tier and dependency analysis

- [ ] Calculate supplier tiers relative to the selected manufacturing organization.
- [ ] Implement upstream dependency traversal.
- [ ] Implement downstream impact traversal.
- [ ] Handle suppliers reachable through multiple paths.
- [ ] Detect cycles or invalid network structures and handle them safely.
- [ ] Add tests for tier calculation and traversal.

**Acceptance criteria**

- The automotive sample chain is assigned the expected tiers relative to its manufacturer.
- Upstream and downstream traversal return the correct connected suppliers.
- Tier values are not treated as globally fixed across different organizations.
- Cycles and disconnected suppliers do not crash graph processing.

### TASK-010: Expose supplier graph APIs

- [ ] Implement the graph endpoints defined in `API_SPEC.md`.
- [ ] Return nodes and edges in the response structure expected by the frontend.
- [ ] Include tier and risk attributes only when available.
- [ ] Support documented filters.
- [ ] Validate graph responses against sample data.

**Acceptance criteria**

- The frontend can retrieve the supplier network through the API.
- Node and edge identifiers are stable and usable by React Flow.
- Graph responses agree with the database and graph service.

---

## Phase 5 – Frontend Foundation

**Goal:** Build the common application shell before adding individual feature screens.

### TASK-011: Implement the application layout

- [ ] Create the sidebar.
- [ ] Create the top navigation bar.
- [ ] Create the main content layout.
- [ ] Add routes for all pages listed in `DESIGN_SYSTEM.md`.
- [ ] Add active navigation states.
- [ ] Add a responsive sidebar and mobile navigation.
- [ ] Apply the shared design tokens.

**Acceptance criteria**

- All planned pages can be opened through navigation.
- The layout follows `DESIGN_SYSTEM.md`.
- The layout adapts to desktop, tablet and mobile widths.

### TASK-012: Implement shared UI components

- [ ] Build reusable KPI cards.
- [ ] Build risk and tier badges.
- [ ] Build buttons, modals and detail panels.
- [ ] Build loading, empty and error states.
- [ ] Build toast notifications.
- [ ] Apply consistent typography, spacing and borders.

**Acceptance criteria**

- Shared components use the design tokens.
- Components have clear loading, empty and error behaviour where relevant.
- Risk is not communicated through color alone.

### TASK-013: Connect frontend API services

- [ ] Create a centralized API service module.
- [ ] Configure the API base URL.
- [ ] Implement reusable request and error handling.
- [ ] Connect the frontend to the supplier and graph APIs.
- [ ] Avoid hardcoding live-looking values in data-driven screens.

**Acceptance criteria**

- Supplier data is loaded from the backend.
- API failures are shown in a useful error state.
- No secret or backend credential is exposed in frontend code.

---

## Phase 6 – Supplier Directory and Network UI

**Goal:** Let users explore the supplier ecosystem.

### TASK-014: Build the Supplier Directory

- [ ] Display supplier records in a table.
- [ ] Add supplier name search.
- [ ] Add tier and risk filters where data is available.
- [ ] Add sorting and pagination.
- [ ] Add a supplier detail view.
- [ ] Show empty and error states.

**Acceptance criteria**

- Directory rows come from the supplier API.
- Search and filters operate on the returned supplier data.
- Selecting a supplier opens the correct supplier details.

### TASK-015: Build the interactive Supplier Network

- [ ] Render API-provided nodes and edges using React Flow.
- [ ] Visually distinguish Tier 1, Tier 2 and Tier 3.
- [ ] Display risk styling only when a risk value exists.
- [ ] Add graph zoom, pan and fit-to-view controls.
- [ ] Add a tier and risk legend.
- [ ] Add supplier search and graph filtering.
- [ ] Open a supplier detail panel when a node is selected.
- [ ] Show upstream and downstream connections.

**Acceptance criteria**

- The graph matches the backend network.
- Selecting a node displays the correct supplier.
- Users can navigate and inspect the sample multi-tier network.
- The graph remains usable with a larger sample dataset.
- Unknown risk values are not displayed as confirmed low risk.

### TASK-016: Build the Overview Dashboard

- [ ] Add supplier count cards.
- [ ] Add tier distribution.
- [ ] Add risk distribution when risk data is available.
- [ ] Add recent alerts when alert data is available.
- [ ] Add a supplier network summary.
- [ ] Add recent activity only when activity records are available.
- [ ] Label synthetic demonstration data clearly.

**Acceptance criteria**

- Dashboard metrics are calculated from API data.
- Unavailable metrics show an appropriate empty or unavailable state.
- Sample data is clearly identified as synthetic.

---

## Phase 7 – Risk Intelligence

**Goal:** Identify and explain risks using available evidence and documented rules.

### TASK-017: Define and implement risk rules

- [ ] Review the risk requirements in `PRD.md`, `ARCHITECTURE.md` and `API_SPEC.md`.
- [ ] Define the supported disruption categories.
- [ ] Implement the documented risk classification method.
- [ ] Keep risk calculations in a dedicated service.
- [ ] Make thresholds configurable where appropriate.
- [ ] Record the reason and supporting evidence for each assessment.
- [ ] Handle insufficient information explicitly.

**Acceptance criteria**

- The same inputs produce consistent results under the same rule configuration.
- Every risk classification has an explainable reason.
- Missing evidence is not treated as proof of safety.
- Risk scores are not presented as probabilities unless a valid probability method is implemented.

### TASK-018: Implement risk alert APIs and UI

- [ ] Implement the risk endpoints defined in `API_SPEC.md`.
- [ ] Build risk summary cards.
- [ ] Build the risk alert list.
- [ ] Add severity and category filters.
- [ ] Build the alert detail view.
- [ ] Display source evidence and timestamps.
- [ ] Link alerts to affected suppliers.

**Acceptance criteria**

- Users can retrieve and inspect risk alerts.
- Each alert identifies its supplier and supporting evidence where available.
- Detected, predicted and simulated risks are visibly distinguished.

---

## Phase 8 – Impact Analysis

**Goal:** Explain which downstream suppliers and manufacturing operations could be affected by a disruption.

### TASK-019: Implement downstream impact analysis

- [ ] Accept a selected supplier or disruption as input.
- [ ] Traverse downstream relationships using the graph service.
- [ ] Identify potentially affected suppliers.
- [ ] Identify related materials and components where the data supports it.
- [ ] Identify production lines only when the required relationships exist.
- [ ] Record assumptions and unavailable information.
- [ ] Add tests using the synthetic automotive network.

**Acceptance criteria**

- Direct and indirect downstream effects are distinguished.
- Results are traceable to stored supplier relationships.
- The service does not claim a production stoppage without supporting data.
- Missing inventory, capacity or production information is clearly identified.

### TASK-020: Build the Impact Analysis screen

- [ ] Display the selected disruption and supplier.
- [ ] Highlight affected paths in the supplier graph.
- [ ] List directly and indirectly affected suppliers.
- [ ] Show affected materials and components where available.
- [ ] Show potentially affected production lines where supported.
- [ ] Display assumptions and limitations.

**Acceptance criteria**

- The screen presents the backend impact results.
- A user can understand why each supplier is included.
- Potential impact is not presented as confirmed actual damage.

---

## Phase 9 – Document Intelligence

**Goal:** Extract supplier information from procurement documents and let users review it.

### TASK-021: Implement document upload and validation

- [ ] Implement the upload endpoint defined in `API_SPEC.md`.
- [ ] Validate supported file types.
- [ ] Enforce upload-size limits.
- [ ] Generate safe stored filenames.
- [ ] Store document metadata.
- [ ] Track processing status.
- [ ] Handle invalid and unreadable files.

**Acceptance criteria**

- Supported sample documents can be uploaded.
- Invalid files are rejected safely.
- Upload status and document metadata can be retrieved.
- Uploaded files are never executed.

### TASK-022: Implement text extraction

- [ ] Extract text from supported document formats.
- [ ] Preserve the source document reference.
- [ ] Handle empty or unreadable documents.
- [ ] Return structured extraction input for the AI extraction service.
- [ ] Add tests using sample procurement documents.

**Acceptance criteria**

- Text can be extracted from supported sample documents.
- Extraction failures are reported clearly.
- Source document references remain attached to extracted results.

### TASK-023: Implement AI supplier extraction

- [ ] Define a structured extraction schema.
- [ ] Extract supplier names and buyer names.
- [ ] Extract materials and components.
- [ ] Extract possible supplier relationships.
- [ ] Preserve supporting text or source location where available.
- [ ] Record confidence values only when the extraction method provides them.
- [ ] Flag ambiguous or incomplete results.
- [ ] Handle model or provider errors.

**Acceptance criteria**

- Extraction returns validated structured data.
- Unsupported or missing fields are not guessed.
- Ambiguous relationships are flagged for review.
- The AI provider and credentials are configured outside source code.

### TASK-024: Build the extraction review workflow

- [ ] Display extracted fields in an editable review screen.
- [ ] Show the source document.
- [ ] Allow users to correct extracted values.
- [ ] Allow users to confirm or reject proposed relationships.
- [ ] Save confirmed information through the documented API.
- [ ] Update the supplier graph after confirmed relationships are saved.

**Acceptance criteria**

- Extracted information is not automatically treated as verified.
- Users can correct and confirm records.
- Rejected information does not become a confirmed supplier relationship.
- The graph reflects saved, confirmed relationships.

---

## Phase 10 – Scenario Simulator

**Goal:** Let users explore hypothetical disruptions without changing real supplier records.

### TASK-025: Implement the simulation service

- [ ] Define supported simulation inputs.
- [ ] Validate the selected supplier and disruption type.
- [ ] Use the graph service to identify affected downstream suppliers.
- [ ] Calculate outputs using available business data.
- [ ] Identify possible alternatives only when the required supplier information exists.
- [ ] Store simulation inputs and results separately from actual risk records.
- [ ] Label unsupported calculations and assumptions.

**Acceptance criteria**

- A simulation can be run for a valid sample supplier.
- Results are reproducible for the same inputs and data.
- Simulation does not modify confirmed supplier records.
- Missing capacity or inventory information is clearly reported.

### TASK-026: Build the Scenario Simulator UI

- [ ] Add supplier selection.
- [ ] Add disruption type selection.
- [ ] Add disruption duration and supported parameters.
- [ ] Add a run simulation action.
- [ ] Display affected suppliers and materials.
- [ ] Display potential production impact where supported.
- [ ] Display alternative options only when supported by data.
- [ ] Add scenario comparison if supported by the API.
- [ ] Clearly label all results as hypothetical.

**Acceptance criteria**

- Users can submit a valid scenario.
- Results are displayed from the simulation API.
- Actual risk records and supplier data remain unchanged.
- Hypothetical results cannot be mistaken for confirmed disruptions.

---

## Phase 11 – Reports and Final Integration

**Goal:** Present the prototype's findings in a useful, consistent format.

### TASK-027: Implement reports

- [ ] Build a supplier network summary.
- [ ] Include tier distribution.
- [ ] Include risk summaries where data exists.
- [ ] Include high-risk suppliers and supporting evidence.
- [ ] Include impact analysis results.
- [ ] Include simulation results with clear hypothetical labels.
- [ ] Implement export formats only where supported by the project scope.

**Acceptance criteria**

- Reports use stored application data.
- Missing information is identified rather than fabricated.
- Simulated outcomes are clearly separated from actual records.
- Exported reports are readable and consistent with the on-screen results.

### TASK-028: Complete end-to-end integration

- [ ] Verify frontend-to-backend communication.
- [ ] Verify database-to-API consistency.
- [ ] Verify supplier-to-graph consistency.
- [ ] Verify document review updates the graph.
- [ ] Verify risk alerts link to the correct suppliers.
- [ ] Verify impact analysis uses the correct graph direction.
- [ ] Verify simulation results remain separate from actual records.
- [ ] Fix integration errors.

**Acceptance criteria**

The complete demonstration workflow can be performed without manually editing the database:

```text
Load Synthetic Sample Data
          |
          v
View Supplier Directory
          |
          v
Explore Multi-Tier Supplier Network
          |
          v
Select or Record a Disruption
          |
          v
View Risk Assessment
          |
          v
Analyse Downstream Impact
          |
          v
Run a Hypothetical Scenario
          |
          v
Review Results and Reports
```

Document upload and extraction should also be demonstrated as a separate workflow that adds reviewed supplier information to the network.

---

## Phase 12 – Quality, Security and Demo Readiness

### TASK-029: Backend testing

- [ ] Add or complete pytest tests for database operations.
- [ ] Test supplier and relationship endpoints.
- [ ] Test graph construction and traversal.
- [ ] Test tier identification.
- [ ] Test risk classification.
- [ ] Test impact analysis.
- [ ] Test document validation and extraction handling.
- [ ] Test scenario simulation.
- [ ] Verify error responses.

**Acceptance criteria**

- Tests cover the core business logic and API paths.
- Test results are recorded accurately.
- Known failures are documented rather than hidden.

### TASK-030: Frontend testing and usability checks

- [ ] Test page navigation.
- [ ] Test loading, empty and error states.
- [ ] Test search and filters.
- [ ] Test supplier graph interactions.
- [ ] Test document upload and review.
- [ ] Test simulation submission and results.
- [ ] Check responsive layouts.
- [ ] Check keyboard navigation and visible focus states.

**Acceptance criteria**

- Core user workflows can be completed through the UI.
- Errors are understandable.
- Important controls are usable on supported screen sizes.

### TASK-031: Security and configuration review

- [ ] Check that secrets are not committed.
- [ ] Check environment configuration.
- [ ] Check file upload validation and limits.
- [ ] Check database query parameterization.
- [ ] Check error responses for information leakage.
- [ ] Check that uploaded documents are not executed.
- [ ] Check that protected operations are access-controlled if authentication is implemented.

**Acceptance criteria**

- No known credentials are hardcoded or committed.
- File uploads are validated.
- Sensitive internal details are not returned to users.
- Remaining security limitations are documented.

### TASK-032: Prepare the demonstration

- [ ] Create a repeatable sample-data setup.
- [ ] Prepare a short demonstration sequence.
- [ ] Demonstrate the Tier 1, Tier 2 and Tier 3 supplier chain.
- [ ] Demonstrate a sample upstream disruption.
- [ ] Show the affected downstream suppliers.
- [ ] Show the impact analysis.
- [ ] Run a hypothetical disruption scenario.
- [ ] Explain which information is synthetic and which results are calculated.
- [ ] Record known limitations.

**Acceptance criteria**

- A fresh local setup can run the demonstration using the documented instructions.
- The demonstration does not depend on undocumented manual database changes.
- Sample data and hypothetical results are clearly labelled.

---

## 5. Minimum Working Prototype – Definition of Done

The first usable prototype is complete when all of the following are true:

- [ ] Frontend and backend run locally.
- [ ] SQLite initializes and contains synthetic automotive supplier data.
- [ ] Supplier records can be retrieved through the API.
- [ ] Supplier relationships are represented in a directed NetworkX graph.
- [ ] Tier 1, Tier 2 and Tier 3 can be explored relative to the manufacturer.
- [ ] The React frontend displays the supplier directory.
- [ ] The React Flow graph displays the multi-tier network.
- [ ] Selecting a supplier shows its details.
- [ ] A sample disruption can be assessed using documented risk rules.
- [ ] Downstream potentially affected suppliers can be identified.
- [ ] The UI distinguishes evidence-based findings from hypothetical outcomes.
- [ ] Core backend tests pass.
- [ ] Setup and demonstration instructions are documented.

Document extraction, scenario simulation and reporting can follow as the next milestone if time is limited, but they remain part of the planned product scope.

---

## 6. Recommended First AI Coding Agent Prompt

Use this prompt when starting implementation:

> Read `AGENTS.md`, `PRD.md`, `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `API_SPEC.md`, `DESIGN_SYSTEM.md` and `TASKS.md` before changing any code.
>
> Start with TASK-001. Inspect the existing repository and report the current structure, existing implementation, missing pieces and any conflicts between the documentation.
>
> Do not implement every phase at once. Work in task order and begin with the repository and environment setup. Before each significant change, identify the files that will be affected. Preserve existing work, follow the documented stack and API contracts, and test each completed task.
>
> Use synthetic automotive supplier data for the first working demonstration. Do not invent supplier relationships or risk evidence. Mark a task complete only after checking its acceptance criteria. Report any blockers or documentation conflicts instead of silently making assumptions.

---

## 7. Progress Tracking

Update this section as development proceeds.

| Phase | Status | Notes |
|---|---|---|
| 1. Repository and environment setup | Not started | |
| 2. Database and sample data | Not started | |
| 3. Supplier management API | Not started | |
| 4. Supplier graph engine | Not started | |
| 5. Frontend foundation | Not started | |
| 6. Supplier directory and network UI | Not started | |
| 7. Risk intelligence | Not started | |
| 8. Impact analysis | Not started | |
| 9. Document intelligence | Not started | |
| 10. Scenario simulator | Not started | |
| 11. Reports and final integration | Not started | |
| 12. Quality and demo readiness | Not started | |

Use these status values:

- `Not started`
- `In progress`
- `Blocked`
- `Completed`

Update the status only after checking the work completed.

---

## Final Development Principle

**Build the data foundation first, make the supplier network work second, and add AI-driven intelligence on top of verified supplier relationships.**

A reliable, explainable prototype is more valuable than a large collection of screens that are not connected to working data and backend logic.
