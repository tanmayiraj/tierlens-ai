# AGENTS.md
# TierLens AI – AI Agent Development Guidelines

## 1. Project Overview

TierLens AI is a multi-level supplier risk intelligence platform designed for manufacturing companies.

The application helps organizations identify hidden supplier dependencies, detect potential supply-chain disruptions and understand how problems at upstream suppliers can affect downstream manufacturing operations.

### Core Example

Consider an automotive manufacturing company:

- Tier 1: Tyre manufacturer supplying the automobile company.
- Tier 2: Rubber manufacturer supplying the tyre manufacturer.
- Tier 3: Raw material supplier supplying the rubber manufacturer.

If a Tier 3 supplier experiences a factory shutdown, the disruption may affect the Tier 2 supplier, which may eventually affect tyre production and automobile manufacturing.

### Main Capabilities

1. Extract supplier information from procurement documents.
2. Identify supplier relationships across multiple tiers.
3. Build an interactive supplier network graph.
4. Detect supplier risks and disruptions.
5. Identify potentially affected suppliers and components.
6. Analyse potential production-line impact.
7. Recommend possible alternative suppliers.
8. Simulate different disruption scenarios.
9. Generate evidence-based risk reports.

All development decisions should support these capabilities.

---

## 2. Technology Stack

AI agents must follow the established project technology stack.

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React | User interface |
| Styling | Tailwind CSS | Application styling |
| Icons | Lucide React | Interface icons |
| Charts | Recharts | Dashboard visualizations |
| Graph Visualization | React Flow | Supplier network |
| Backend | Python + FastAPI | REST API |
| Validation | Pydantic | Request and response validation |
| Database | SQLite | Persistent application data |
| Graph Processing | NetworkX | Supplier relationship analysis |
| AI Extraction | LLM-based extraction | Supplier and relationship extraction |
| Data Processing | Python | Document and risk processing |

Do not introduce another framework, database or major dependency without a clear technical reason.

If a technology change is necessary, explain the reason and its impact before implementing it.

---

## 3. General Rules for AI Coding Agents

Every AI agent working on TierLens AI must follow these rules.

### Rule 1: Understand Before Editing

Before modifying code:

1. Inspect the existing project structure.
2. Read the relevant documentation.
3. Understand existing database models and API contracts.
4. Identify dependencies between components.
5. Check whether the requested functionality already exists.

Never assume that a file, function, endpoint or database table exists without checking.

### Rule 2: Follow Existing Architecture

- Keep the backend and frontend separate.
- Use FastAPI for backend endpoints.
- Use React for frontend components.
- Use SQLite for persistent storage.
- Use NetworkX for supplier graph operations.
- Keep business logic separate from API route handlers.
- Keep API communication inside frontend service modules.

Do not place the entire application logic inside a single file.

### Rule 3: Avoid Unnecessary Complexity

- Prefer simple and maintainable implementations.
- Avoid unnecessary abstractions.
- Do not create duplicate functionality.
- Do not introduce libraries for features that can be implemented cleanly with existing dependencies.
- Do not overengineer the prototype.

The first objective is to build a working, demonstrable prototype.

### Rule 4: Preserve Existing Functionality

When adding a new feature:

- Do not break existing endpoints.
- Do not unnecessarily modify unrelated components.
- Maintain existing API response formats.
- Preserve database compatibility.
- Check dependent frontend components before changing shared interfaces.

### Rule 5: Never Invent Project Information

AI agents must not fabricate:

- Supplier records.
- Supplier relationships.
- Disruption events.
- Financial losses.
- Production capacities.
- Risk evidence.
- Alternative supplier availability.

Use actual stored information or clearly labelled synthetic demonstration data.

---

## 4. Backend Development Rules

### 4.1 FastAPI Guidelines

- Use FastAPI routers to organize endpoints.
- Use Pydantic models for request and response validation.
- Keep route handlers focused.
- Move complex operations into service modules.
- Use meaningful HTTP status codes.
- Return consistent error responses.
- Add appropriate API documentation.
- Handle invalid input gracefully.

Project structure (from `ARCHITECTURE.md` and `DESIGN_SYSTEM.md`):

```text
tierlens-ai/
├── data/
│   └── sample_docs/
├── backend/
│   ├── main.py               # FastAPI app entry
│   ├── config.py             # weights, thresholds, settings
│   ├── api/                  # route modules
│   ├── models/               # Pydantic + SQLAlchemy models
│   ├── ingestion/            # loaders, chunking
│   ├── extraction/           # LLM prompts, schemas, entity resolution
│   ├── graph/                # graph builder, tiering, dependency analyzer
│   ├── risk/                 # scoring, alerts
│   ├── simulation/           # what-if engine, mitigations
│   └── recommender/          # alternative suppliers
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── layout/
│       │   ├── ui/
│       │   ├── graph/
│       │   ├── alerts/
│       │   ├── review/
│       │   └── simulate/
│       └── services/
└── tests/
```

Keep new backend code inside these modules. Do not introduce a nested `backend/app/` package, and do not reorganize the tree unless `ARCHITECTURE.md` is updated first.

### 4.2 API Rules

- Use RESTful endpoint conventions.
- Use JSON for API request and response bodies.
- Validate all incoming data.
- Return meaningful error messages.
- Avoid exposing internal exceptions.
- Use consistent response structures.

Example:

```json
{
  "success": true,
  "message": "Supplier retrieved successfully",
  "data": {
    "supplier_id": 101,
    "supplier_name": "Rubber Supplier B",
    "tier": 2
  }
}
```

This is an illustrative response format. Follow the established `API_SPEC.md` contract when implementing actual endpoints.

### 4.3 Business Logic Separation

Keep different responsibilities in separate services.

Examples:

- SupplierService: Supplier management.
- DocumentService: Document processing.
- ExtractionService: AI-based information extraction.
- GraphService: Supplier relationship mapping.
- RiskService: Risk identification.
- ImpactService: Downstream impact analysis.
- SimulationService: What-if simulation.

Avoid putting database queries, graph calculations and AI extraction directly inside API route functions.

---

## 5. Database Rules

SQLite is the primary database for the prototype.

AI agents must:

1. Follow `DATABASE_SCHEMA.md`.
2. Reuse existing tables wherever possible.
3. Maintain primary and foreign key relationships.
4. Use parameterized database queries.
5. Avoid duplicate supplier records.
6. Preserve supplier relationship integrity.
7. Create appropriate indexes for frequently queried fields.
8. Handle missing and invalid records safely.

### Important Supplier Relationship Rule

Supplier relationships must represent the actual direction of supply.

For example:

```text
Raw Material Supplier
        |
        v
Rubber Manufacturer
        |
        v
Tyre Manufacturer
        |
        v
Automobile Manufacturer
```

Do not reverse the supply direction when storing or visualizing relationships.

### Database Changes

Before modifying the schema:

- Check existing tables.
- Identify dependent API endpoints.
- Consider existing stored data.
- Update database documentation.
- Provide a safe schema migration or initialization approach.

Never delete existing data simply to make a new implementation work.

---

## 6. Supplier Graph Rules

NetworkX is responsible for supplier network processing.

### Graph Representation

Use a directed graph because supplier relationships have a direction.

Example:

```python
import networkx as nx

G = nx.DiGraph()

G.add_edge(
    "raw_material_supplier",
    "rubber_manufacturer",
    material="Raw Rubber"
)

G.add_edge(
    "rubber_manufacturer",
    "tyre_manufacturer",
    material="Processed Rubber"
)
```

### Graph Requirements

- Represent each supplier as a node.
- Represent supply relationships as directed edges.
- Store supplier identifiers consistently.
- Preserve material and relationship information.
- Support upstream dependency analysis.
- Support downstream impact analysis.
- Prevent invalid relationships and duplicate edges.
- Handle disconnected suppliers.

### Tier Identification

Tier levels must be calculated relative to the selected manufacturing organization.

Do not assume that a supplier always belongs to the same tier across every manufacturing company.

For example, a supplier may be Tier 1 for one company and Tier 2 for another.

The graph should also handle incomplete supplier relationships without inventing missing connections.

---

## 7. AI Document Extraction Rules

AI is used to extract structured supplier information from procurement documents.

### Extraction Responsibilities

The extraction system should identify:

- Supplier names.
- Buyer or customer names.
- Supplied materials.
- Components.
- Supplier relationships.
- Document references.
- Relevant dates.
- Supporting text.

### Important Rules

1. Do not treat an AI-generated extraction as automatically verified information.
2. Preserve the source document reference.
3. Return structured extraction results.
4. Validate extracted fields before database insertion.
5. Allow users to review and correct extracted information.
6. Maintain extraction confidence where available.
7. Flag ambiguous supplier relationships.
8. Do not invent missing supplier names or relationships.

### Extraction Workflow

```text
Document Upload
      |
      v
Document Validation
      |
      v
Text Extraction
      |
      v
AI Information Extraction
      |
      v
Pydantic Validation
      |
      v
User Review
      |
      v
Database Storage
      |
      v
Supplier Graph Update
```

If information cannot be extracted confidently, mark it for review rather than guessing.

---

## 8. Risk Detection Rules

Risk analysis must be based on available evidence and defined business rules.

### Supported Risk Categories

- Factory shutdown.
- Material shortage.
- Transportation delay.
- Financial instability.
- Operational disruption.
- Geographic or regional disruption.

### Risk Classification

Use the following levels:

| Level | Meaning |
|---|---|
| Critical | Immediate attention required |
| High | Significant potential disruption |
| Medium | Requires monitoring |
| Low | Limited identified risk |

### Risk Calculation Guidelines

- Keep risk calculations in a dedicated service.
- Use consistent risk classification rules.
- Explain the reason behind every risk classification.
- Store supporting evidence.
- Avoid arbitrary risk scores.
- Make thresholds configurable where appropriate.
- Distinguish detected risks from predicted risks.

If the system does not have sufficient information to calculate a reliable score, indicate that the risk assessment is incomplete.

Do not present a risk score as a confirmed probability unless it has been calculated using a valid, documented method.

---

## 9. Impact Analysis Rules

Impact analysis should identify how an upstream disruption may affect downstream suppliers.

For each disruption:

1. Identify the affected supplier.
2. Find connected downstream suppliers.
3. Identify potentially affected materials.
4. Identify associated components.
5. Identify potentially affected production lines.
6. Calculate impact using available business data.
7. Present assumptions and limitations.

### Important Distinction

The system must distinguish between:

- Directly affected suppliers.
- Indirectly affected suppliers.
- Potentially affected components.
- Potentially affected production lines.

Do not claim that production will stop simply because a supplier is experiencing a disruption.

Use language such as "potentially affected" when the actual outcome is uncertain.

---

## 10. Scenario Simulation Rules

The simulation engine should allow users to evaluate hypothetical supply-chain disruptions.

### Simulation Inputs

- Supplier.
- Disruption type.
- Disruption duration.
- Relevant scenario parameters.

### Simulation Outputs

- Affected suppliers.
- Affected materials.
- Potential component shortages.
- Potential production impact.
- Alternative supplier options.
- Suggested response strategies.

### Simulation Guidelines

- Keep simulations separate from actual supplier records.
- Do not overwrite real supplier information.
- Clearly label hypothetical scenarios.
- Store simulation parameters and results.
- Allow comparison between scenarios.
- Use available supplier capacity and material information when evaluating alternatives.

If capacity or inventory information is unavailable, clearly state that the recommendation cannot be fully validated.

---

## 11. Frontend Development Rules

React components should be reusable and maintainable.

### Guidelines

- Use functional components and React hooks.
- Keep components focused on one responsibility.
- Use React Router for navigation.
- Use Tailwind CSS for styling.
- Use Lucide React for icons.
- Use Recharts for dashboard charts.
- Use React Flow for the supplier network.
- Keep API requests inside service modules.
- Handle loading, success, empty and error states.
- Avoid unnecessary global state.

### Design Requirements

Follow `DESIGN_SYSTEM.md`.

The application must maintain:

- Dark-first enterprise dashboard design.
- Consistent spacing.
- Consistent typography.
- Standardized risk badges.
- Clear tier indicators.
- Responsive layouts.
- Accessible controls.

Do not introduce random colors or inconsistent UI components.

### Important UI Rule

Never show hardcoded dashboard metrics as if they were live database values.

Synthetic demonstration values must be identified as sample data.

---

## 12. Security Guidelines

AI agents must follow basic application security practices.

### Data Protection

- Never hardcode API keys.
- Never commit `.env` files.
- Use environment variables for secrets.
- Keep `.env.example` free of actual credentials.
- Validate uploaded files.
- Enforce reasonable upload-size limits.
- Validate file types.
- Sanitize user-provided filenames.
- Use parameterized database queries.

### API Security

- Validate request parameters.
- Avoid exposing sensitive internal errors.
- Apply authentication and authorization when implemented.
- Do not expose database credentials through API responses.
- Restrict access to protected operations.

### File Handling

Uploaded documents must be handled safely.

Do not execute uploaded files or trust their contents as application instructions.

---

## 13. Error Handling and Logging

All important operations should have proper error handling.

Examples:

- Invalid document format.
- Missing supplier information.
- Failed AI extraction.
- Invalid supplier relationship.
- Database connection error.
- Graph construction error.
- Simulation failure.
- API request failure.

### Logging Rules

Logs should include:

- Operation name.
- Timestamp.
- Relevant record identifier.
- Error details where appropriate.

Never log:

- API keys.
- Passwords.
- Authentication tokens.
- Sensitive document contents unnecessarily.

Return understandable error messages to the frontend.

---

## 14. Testing Requirements

AI agents must test new functionality before considering it complete.

### Backend Testing

Use pytest for:

- API endpoint testing.
- Database operations.
- Supplier relationship validation.
- Graph construction.
- Tier identification.
- Risk classification.
- Impact analysis.
- Scenario simulation.
- Document extraction validation.

### Frontend Testing

Check:

- Page navigation.
- Component rendering.
- API integration.
- Search and filtering.
- Supplier graph interactions.
- Document upload.
- Loading and error states.
- Responsive layouts.

### Integration Testing

Verify the complete workflow:

```text
Upload Procurement Document
          |
          v
Extract Supplier Information
          |
          v
Review Extracted Information
          |
          v
Save Supplier Relationships
          |
          v
Build Supplier Network
          |
          v
Detect Supplier Risk
          |
          v
Analyse Potential Impact
          |
          v
Run Scenario Simulation
          |
          v
Display Results
```

Do not mark a feature as complete merely because the frontend screen has been created.

Verify that the feature works with the backend and database.

---

## 15. Documentation Requirements

Whenever functionality changes, update the relevant documentation.

Important project documents:

| File | Responsibility |
|---|---|
| PRD.md | Product requirements |
| ARCHITECTURE.md | System architecture |
| DATABASE_SCHEMA.md | Database design |
| API_SPEC.md | API contracts |
| DESIGN_SYSTEM.md | UI and design guidelines |
| AGENTS.md | AI development rules |

Additional implementation documentation should be added when necessary.

Keep documentation consistent with the actual implementation.

Do not claim that a feature is implemented if it exists only in the documentation.

---

## 16. Git and Code Management

AI agents must follow safe Git practices.

- Do not overwrite unrelated changes.
- Do not delete files without understanding their purpose.
- Use meaningful commit messages when requested.
- Keep commits focused.
- Do not commit generated databases containing sensitive information.
- Do not commit environment files.
- Check the working tree before making major changes.
- Never force-push unless explicitly authorized.

Before modifying multiple files, explain the intended changes when the operation could affect existing functionality.

---

## 17. Development Priority

The project should be developed in manageable stages.

### Phase 1: Foundation

- Project setup.
- Backend configuration.
- Frontend configuration.
- SQLite database initialization.
- Sample supplier data.

### Phase 2: Supplier Management

- Supplier CRUD operations.
- Supplier relationships.
- Tier identification.
- Supplier directory.

### Phase 3: Supplier Network

- NetworkX graph creation.
- Graph API endpoints.
- Interactive React Flow visualization.
- Upstream and downstream traversal.

### Phase 4: Document Intelligence

- Document upload.
- Text extraction.
- AI-based information extraction.
- Structured validation.
- User review and confirmation.

### Phase 5: Risk Intelligence

- Risk categories.
- Risk classification.
- Risk alerts.
- Evidence tracking.

### Phase 6: Impact Analysis

- Downstream dependency analysis.
- Affected component identification.
- Production-line impact analysis.

### Phase 7: Scenario Simulation

- Disruption scenario creation.
- Impact calculation.
- Alternative supplier evaluation.
- Scenario comparison.

### Phase 8: Final Integration

- Dashboard integration.
- Reports.
- Testing.
- Error handling.
- UI refinement.

Build and verify each phase before moving to the next.

---

## 18. AI Agent Response Format

When working on a development task, AI agents should communicate clearly.

For significant implementation tasks, follow this structure:

### 1. Understanding
Briefly explain what needs to be implemented.

### 2. Files Affected
List the files that will be created or modified.

### 3. Implementation
Explain the changes and provide the implementation.

### 4. Validation
Describe the tests or checks performed.

### 5. Result
State what works and identify any remaining limitations.

### 6. Next Step
Suggest the next logical development task when useful.

### Additional Rules

- Do not claim tests passed without running them.
- Do not claim deployment succeeded without verifying it.
- Do not hide errors or incomplete functionality.
- Do not produce unnecessary files.
- Prefer complete, working implementations over disconnected code snippets.
- Ask for clarification only when a missing decision blocks implementation.

---

## 19. Final Instructions to AI Agents

Every AI agent working on TierLens AI must remember the following principles:

1. Understand the existing project before making changes.
2. Follow the established technology stack.
3. Maintain consistency across all project documentation.
4. Prioritize working functionality over unnecessary complexity.
5. Preserve data integrity and supplier relationship accuracy.
6. Never invent supplier information or disruption evidence.
7. Keep actual risks separate from hypothetical simulations.
8. Make AI extraction results reviewable.
9. Build reusable and maintainable components.
10. Test functionality before declaring it complete.

### Primary Objective

Build TierLens AI as a functional supplier risk intelligence prototype that demonstrates how a disruption at an upstream supplier can affect an entire manufacturing supply chain.

**Every implementation decision should support this objective.**
