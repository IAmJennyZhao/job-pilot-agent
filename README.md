# CareerPilot Agent

FastAPI + Next.js MVP foundation for an AI-assisted job search dashboard.

## Running

From the repo root:

```powershell
.\pilot.ps1 dev
```

Starts backend and frontend in the current terminal. In VS Code, run this from the integrated terminal or use `Tasks: Run Task -> CareerPilot: dev`. Stop both servers with `Ctrl+C`.

Pilot modes:

```powershell
.\pilot.ps1 dev          # backend + frontend in the current terminal
.\pilot.ps1 dev-windows  # backend + frontend in separate visible PowerShell windows
.\pilot.ps1 status       # show whether ports 3000 and 8000 are occupied
.\pilot.ps1 backend      # backend only on http://localhost:8000
.\pilot.ps1 frontend     # frontend only on http://localhost:3000
.\pilot.ps1 test         # backend tests + frontend typecheck
.\pilot.ps1 build        # backend tests + frontend typecheck + frontend production build
```

## Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python scripts\seed.py
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

The seed script resets the local SQLite dev database (recreated via Alembic migrations) before inserting fresh demo data.

Database schema is managed by Alembic only. Migrations run automatically at startup (`alembic upgrade head`); set `AUTO_MIGRATE=0` to disable. To add a schema change: edit `app/models.py`, then `alembic revision --autogenerate -m "describe change"` from `backend/` and review the generated file. The test suite verifies the migrated schema matches the models.

Logs are written to the console and to `backend/logs/app.log` (rotating). Every response carries an `X-Request-ID` header that is also stamped on each log line, and error bodies include a `request_id` field for correlation.

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Run tests:

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Typecheck/build:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Environment

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `OPENAI_MODEL` for AI actions. Set `TAVILY_API_KEY` to enable public web retrieval for company research inside Advanced Detailed Analysis. The app defaults to SQLite at `backend/careerpilot.db` and can switch to Postgres by changing `DATABASE_URL`. Relative SQLite paths in `DATABASE_URL` are anchored to `backend/` regardless of the working directory.

AI actions are synchronous button-triggered calls. If `OPENAI_API_KEY` or `OPENAI_MODEL` is missing, the backend returns a clear `503` and the frontend displays the error. If `TAVILY_API_KEY` is missing or retrieval fails, advanced analysis still uses the normal OpenAI model and saves a limited company research section with a coverage note.

## Week 1 Demo Script

1. Run the backend seed script, then open `/dashboard`.
2. Confirm Active Jobs, Archived, Need Tailoring, Interviewing, and the full status pipeline are populated.
3. Open `/jobs`, scan the table, and note the top gaps column.
4. Toggle Show archived, then restore the archived job by changing its status.
5. Add a new job from the form and confirm the tracker updates.
6. Open the new job detail page, click Edit, update notes/status/details, and save.
7. Return to `/dashboard` and confirm the counts changed.
