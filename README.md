# CareerPilot Agent

FastAPI + Next.js MVP foundation for an AI-assisted job search dashboard.

## Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python scripts\seed.py
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

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

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` for AI actions. The app defaults to SQLite for local development and can switch to Postgres by changing `DATABASE_URL`.

AI actions are synchronous button-triggered calls. If `OPENAI_API_KEY` is missing, the backend returns a clear `503` and the frontend displays the error.

## Week 1 Demo Script

1. Run the backend seed script, then open `/dashboard`.
2. Confirm Active Jobs, Archived, Need Tailoring, Interviewing, and the full status pipeline are populated.
3. Open `/jobs`, scan the table, and note the top gaps column.
4. Toggle Show archived, then restore the archived job by changing its status.
5. Add a new job from the form and confirm the tracker updates.
6. Open the new job detail page, click Edit, update notes/status/details, and save.
7. Return to `/dashboard` and confirm the counts changed.
