# Job Pilot Agent

Job Pilot Agent is a FastAPI + Next.js dashboard for managing the job search with AI-assisted workflows. It tracks opportunities, analyzes job fit, ranks resume assets, plans skill gaps, and supports interview practice from one focused workspace.

## Core Workflows

Job Pilot Agent is organized around three main job-search workflows:

### 1. Search Dashboard

Use the dashboard to track active opportunities, spot stale applications, monitor pipeline movement, and surface missing data, active risks, and priority skill gaps.

Planned demo asset: `docs/assets/dashboard-flow.gif`

![Dashboard demo](docs/assets/dashboard-flow.gif)

### 2. Job Intelligence

Save jobs from pasted descriptions or URLs, extract structured details, flag duplicates, and run AI-assisted analysis for resume fit, company research, interview prep, asset recommendations, skill gaps, and study plans.

![Job intelligence flow demo](docs/assets/job-intelligence-flow.gif)

### 3. Interview Practice

Generate role-specific practice questions, answer them in a guided session, and review feedback, follow-up prompts, score trends, and weak-point insights.

![Interview Practice flow demo](docs/assets/interview-practice-flow.gif)

### 4. Skill Gap Study Planning

Review major skill gaps from saved job analyses, prioritize the highest-impact gaps, and generate study plans tied to target roles.

![Study Plan creation demo](docs/assets/study-plan-demo.gif)


### 5. Interview Practice

Generate role-specific practice questions, answer them in a guided session, and review feedback, follow-up prompts, score trends, and weak-point insights.

![Interview Practice demo](docs/assets/interview-practice.gif)

## Technical Architecture

### Backend

- **FastAPI API layer**: Routers under `backend/app/routers/` expose jobs, profile assets, dashboard summaries, AI actions, skill gaps, study plans, and interview practice.
- **SQLAlchemy domain model**: `backend/app/models.py` defines the job tracker, status events, analyses, resume assets, interview sessions, skill gaps, and saved study plans.
- **Alembic migrations**: Schema state is managed through Alembic, with migrations applied at startup by default and verified by tests.
- **Service layer**: Business workflows live in `backend/app/services/`, including job intake, job health logic, advanced analysis, profile asset ranking, interview practice, research retrieval, and skill-gap aggregation.
- **Structured schemas**: Pydantic models in `backend/app/schemas.py` define request and response contracts for the API and AI outputs.
- **Operational basics**: Request IDs are attached to responses and logs, logs rotate under `backend/logs/`, and local development defaults to SQLite.

### Frontend

- **Next.js App Router**: Routes under `frontend/src/app/` cover the dashboard, jobs, job detail, profile, skills, interview setup, and interview sessions.
- **Typed API client**: `frontend/src/lib/api.ts` centralizes backend calls, error handling, file uploads, downloads, and AI workflow requests.
- **Shared UI primitives**: Reusable buttons, fields, panels, layout shell, theme utilities, and typed frontend models keep screens consistent.
- **Workflow screens**: The UI is organized around job search operations: triage the dashboard, maintain job records, manage profile assets, inspect skill gaps, and practice interviews.

### AI And Agent Ideas

- **Structured output over loose chat**: OpenAI calls request typed outputs for repeatable job extraction, job insights, resume fit, interview prep, resume parsing, asset ranking, and study plans.
- **Human-triggered workflows**: AI actions are explicit button-triggered operations so the user controls cost, timing, and saved results.
- **Retrieval-assisted company research**: Tavily can provide public web snippets for company research; without it, the app falls back to limited context and records the coverage note.
- **Reusable context**: Saved profile assets, job descriptions, status history, previous analyses, and skill gaps feed later workflows instead of treating each action as isolated.
- **Portfolio-safe local default**: The app runs locally with SQLite and environment-based API keys, keeping private job search data out of the repository.

## Running Locally

### Prerequisites

- Python 3.12 or 3.13
- Node.js and npm
- PowerShell if using `pilot.ps1`
- Optional: OpenAI API key for AI actions
- Optional: Tavily API key for public company research

### Environment

Copy `.env.example` to `.env` and fill in values as needed:

```powershell
Copy-Item .env.example .env
```

Important settings:

- `DATABASE_URL` defaults to local SQLite at `backend/careerpilot.db`.
- `OPENAI_API_KEY` and `OPENAI_MODEL` enable AI actions.
- `TAVILY_API_KEY` enables public web retrieval for company research.
- `NEXT_PUBLIC_API_BASE_URL` points the frontend at the backend.

If AI settings are missing, the backend returns a clear `503` for AI actions and the frontend displays the missing requirement.

### One-Command Development

From the repo root:

```powershell
.\pilot.ps1 dev
```

This starts the backend at `http://localhost:8000` and the frontend at `http://localhost:3000` in the current terminal. Stop both with `Ctrl+C`.

Other helper modes:

```powershell
.\pilot.ps1 dev-windows  # backend + frontend in separate visible PowerShell windows
.\pilot.ps1 status       # show whether ports 3000 and 8000 are occupied
.\pilot.ps1 backend      # backend only
.\pilot.ps1 frontend     # frontend only
.\pilot.ps1 test         # backend tests + frontend typecheck
.\pilot.ps1 build        # backend tests + frontend typecheck + frontend production build
```

### Manual Backend Setup

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python scripts\seed.py
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

The seed script resets the local SQLite development database, applies migrations, and inserts demo data.

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Backend tests:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

### Manual Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Database And Migrations

Alembic owns schema changes. Migrations run automatically at backend startup unless `AUTO_MIGRATE=0` is set.

To make a schema change:

```powershell
cd backend
alembic revision --autogenerate -m "describe change"
```

Review the generated migration before committing it. The backend test suite checks that a fresh migrated database matches the SQLAlchemy models and that legacy migration states are handled correctly.
