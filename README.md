# TierLens AI
### Multi-Tier Supplier Risk Intelligence & Disruption Impact Analysis

TierLens AI is an intelligent supply chain risk management platform designed to help automotive manufacturers identify hidden multi-tier supplier dependencies, detect potential disruption risks, and evaluate mitigation strategies.

The platform transforms supplier data and procurement documents into a connected supply chain network, helping decision-makers understand how disruptions at an upstream supplier can affect downstream suppliers, production lines, and revenue.

## Problem Statement

Modern automotive supply chains depend on complex networks of suppliers across multiple tiers. Manufacturers often have visibility into their direct suppliers but limited knowledge of deeper upstream dependencies.

A disruption at a Tier 2 or Tier 3 supplier can create unexpected shortages, production delays, and financial exposure for downstream manufacturers.

Traditional supplier management systems often lack:
- Visibility into multi-tier supplier relationships.
- Identification of hidden and shared supplier dependencies.
- Early understanding of disruption propagation.
- Quantitative evaluation of mitigation strategies.
- A unified view of document-based supplier evidence and risk.

## Proposed Solution

TierLens AI addresses these challenges through a centralized supplier risk intelligence platform.

It provides:
- **Multi-Tier Supplier Mapping:** Visualizes supplier relationships across multiple tiers.
- **Document Intelligence:** Extracts supplier entities, materials, and relationships from procurement documents.
- **Human-in-the-Loop Validation:** Allows users to review and approve AI-extracted relationships.
- **Risk Intelligence:** Identifies supplier concentration, hidden dependencies, and potential disruption exposure.
- **Disruption Simulation:** Evaluates hypothetical supplier failures and their downstream impact.
- **Mitigation Analysis:** Tests alternate suppliers, safety stock, logistics rerouting, and freight expediting.

## Key Features

### 1. Supplier Management
- Centralized supplier directory.
- Supplier profiles with operational details and risk scores.
- Supply tier classification and material capabilities.
- Upstream and downstream supplier relationship tracking.

### 2. Multi-Tier Supply Chain Graph
- Interactive supplier network visualization.
- Identification of Tier 1, Tier 2, and Tier 3 dependencies.
- Visibility into shared upstream suppliers.
- Graph rebuilding based on approved supplier relationships.

### 3. Document Intelligence
- Upload and process procurement documents.
- Extract supplier names, materials, buyers, and relationships.
- Display extracted evidence with source references.
- Track extraction confidence.

### 4. Human-in-the-Loop Review
- Review AI-extracted supplier relationships.
- Approve extracted relationships before graph integration.
- Maintain confidence-based review information.

### 5. Supplier Risk Intelligence
- Five-factor supplier risk scoring.
- Identification of single-source materials.
- Hidden dependency detection.
- Risk alerts and supplier prioritization.

### 6. Disruption Simulator
- Simulate hypothetical supplier disruptions.
- Evaluate downstream production-line impact.
- Calculate revenue exposure and downtime.
- Compare baseline and post-mitigation outcomes.

### 7. Mitigation Strategies
Test different strategies, including:
- Alternate supplier allocation.
- Safety stock injection.
- Inter-tier logistics rerouting.
- Freight expediting.

### 8. Scenario Management
- Save simulation scenarios.
- View previous simulation history.
- Load saved scenarios for further analysis.
- Compare different mitigation configurations.

## Technology Stack

### Frontend
- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Flow – Supplier network visualization
- Recharts – Data visualization and analytics
- Lucide React – Icons

### Backend
- Python 3.12
- FastAPI – REST API development
- SQLAlchemy – Database ORM
- Pydantic – Data validation
- NetworkX – Supply chain graph processing

### Database
- SQLite – Relational data storage

### AI and Document Processing
- Google Gemini API – AI-assisted document extraction
- PyPDF2 – PDF text extraction
- Rule-based and deterministic fallback extraction

### Testing
- Pytest – Backend testing
- TypeScript compiler – Frontend type checking
- Vite – Production build validation

## System Architecture

TierLens AI follows a modular frontend-backend architecture.

### Architecture Components

1. **Frontend Layer**
   - React-based user interface.
   - Communicates with backend services through REST APIs.
   - Displays supplier information, graph visualizations, risk metrics, and simulation results.

2. **Backend Layer**
   - FastAPI handles API requests.
   - SQLAlchemy manages database operations.
   - Business logic processes supplier data, documents, risk calculations, and simulations.

3. **Graph Processing Layer**
   - NetworkX manages supplier relationships.
   - Represents multi-tier supplier dependencies.
   - Supports graph traversal and disruption impact analysis.

4. **Document Intelligence Layer**
   - Processes uploaded procurement documents.
   - Extracts supplier entities and relationships.
   - Supports evidence review and relationship validation.

5. **Simulation Engine**
   - Evaluates hypothetical supplier disruptions.
   - Calculates downstream production impact and revenue exposure.
   - Compares mitigation strategies against baseline scenarios.

6. **Database Layer**
   - SQLite stores supplier records, relationships, documents, and simulation scenarios.

### Project Structure

```text
TierLens-AI/
│
├── backend/
│   ├── api/                 # REST API endpoints
│   ├── graph/               # Supplier graph processing
│   ├── models/              # Database models and schemas
│   ├── services/            # Business logic and AI services
│   ├── config.py            # Backend configuration
│   ├── database.py          # Database connection
│   ├── main.py              # FastAPI application entry point
│   └── seed.py              # Sample database initialization
│
├── frontend/
│   ├── src/                 # React application source
│   ├── .env.example         # Frontend environment template
│   ├── package.json         # Frontend dependencies
│   └── vite.config.ts       # Vite configuration
│
├── data/
│   ├── sample_docs/         # Sample procurement documents
│   └── sample_data.py       # Sample data generation
│
├── uploads/                 # Uploaded documents
├── tests/                   # Backend automated tests
├── project-docs/            # Technical project documentation
├── existing-generated-files/
├── requirements.txt         # Python dependencies
├── .gitignore
├── .env.example          # Backend environment template
├── tierlens.db  # Local SQLite database (generated at runtime)
└── README.md                # Project documentation
```


### 2. Backend Setup

Create and activate a Python virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
pip install -r requirements.txt
```

**Backend Environment Configuration**

The backend loads environment variables from a `.env` file in the project root directory using `python-dotenv`. Create this file only if you need to override the default configuration or configure Gemini AI.

The following variables are supported:

```env
DATABASE_URL=sqlite:///./tierlens.db
GEMINI_API_KEY=your_gemini_api_key
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
DEBUG=true
```

Gemini API configuration is optional. The application supports deterministic fallback extraction when AI services are not configured.

Start the backend server:

```powershell
python -m uvicorn backend.main:app --reload
```

**Backend URL:** `http://127.0.0.1:8000`

**API Documentation:** `http://127.0.0.1:8000/docs`



### 3. Frontend Setup

Open a second terminal and navigate to the frontend directory:

```powershell
cd frontend
npm install
```

Create the frontend environment file by copying the example:

```powershell
Copy-Item .env.example .env
```

The frontend `.env` file should contain:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Start the frontend development server:

```powershell
npm run dev
```

**Frontend URL:** `http://localhost:5173`



### 4. Run Both Services

Keep the backend and frontend running simultaneously in separate terminals.

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://localhost:5173`


## Testing and Verification

TierLens AI includes automated backend tests and frontend build validation.

### Backend Testing

The backend test suite was executed using Pytest.

**Latest verified results:**
- Total tests passed: 238
- Failed tests: 0
- Errors: 0

Run the backend tests using:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Frontend Build Validation

The frontend production build was successfully validated using:

```powershell
cd frontend
npm run build
```

This runs TypeScript compilation and the Vite production build.

### API Health Check

Verify backend connectivity using:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The health endpoint reports:
- Backend status
- Database connectivity
- Supplier graph node and edge counts
- Last graph build timestamp
- LLM configuration status

### Manual Functional Verification

The following workflows were manually verified:

- Dashboard loading and API connectivity.
- Supplier directory and supplier detail navigation.
- Multi-tier graph visualization.
- Document extraction and evidence display.
- Human review queue.
- Baseline disruption simulation.
- Alternate supplier and safety stock mitigation.
- Scenario saving, history, and loading.

## Limitations and Assumptions

- The current platform is a working prototype using sample and synthetic supply chain data.
- Financial exposure and revenue figures generated by simulations are illustrative and not actual company losses.
- Risk scores are prioritization indicators, not statistically calibrated disruption probabilities.
- Document extraction accuracy depends on document quality, format, and available text.
- AI-assisted extraction uses a configured Gemini API key when available. Deterministic fallback extraction is available when AI services are not configured.
- Simulation outcomes depend on the supplier data, relationships, and mitigation assumptions provided.
- The prototype does not guarantee real-world supplier availability or mitigation effectiveness.

## Future Enhancements

Potential improvements include:

1. **Real-Time Risk Monitoring:** Integrate external supplier, logistics, weather, and geopolitical risk data.
2. **Predictive Analytics:** Develop machine-learning models for supplier disruption prediction.
3. **Advanced AI Extraction:** Improve extraction accuracy for complex procurement documents and tables.
4. **ERP Integration:** Connect with enterprise procurement and supply chain management systems.
5. **Advanced Optimization:** Recommend cost-effective mitigation strategies automatically.
6. **Role-Based Access Control:** Introduce administrator, analyst, and procurement user roles.
7. **Cloud Deployment:** Deploy the platform with scalable infrastructure and production-grade database support.
8. **Enhanced Analytics:** Add historical risk trends, supplier performance analysis, and advanced reporting.

## Project Status

TierLens AI is a functional prototype demonstrating multi-tier supplier visibility, document intelligence, risk analysis, disruption simulation, and mitigation evaluation.

