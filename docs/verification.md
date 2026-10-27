# Verification

JobPilot has backend contracts and Chromium desktop/mobile regression suites. Tests use synthetic profiles, source bundles and job records. Normal application storage and external AI services are not used by the browser fixture.

## Run checks

Install backend development dependencies, frontend dependencies, Chromium and TeX Live as described in the [README](../README.md). Then run:

```powershell
# backend
# from backend/
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider

# frontend
# from frontend/
npm run lint
npm run typecheck
node tests/list-editing.cjs
node tests/form-validation.cjs
npm run test:browser
npm run build
```

Run Next.js browser checks and builds sequentially. The browser fixture defaults to ports 3100/8100; set `UI_FRONTEND_PORT=3101` if needed. Fixture databases and rotating logs use separate temporary directories. Pytest uses its own log capture.

## Coverage

- Intake decisions, validation, duplicate confirmation, request keys, evaluated hashes and recovery.
- Saved facts versus analysis provenance; status history and exact filtered drill-downs.
- Reusable editing/Ready/merges, original file downloads, source versions/activation/conflicts.
- Generated revisions, factual review, PDF preview receipts, exact-version approvals and exports, historical compatibility and backups.
- Cohort boundaries/archive populations, proportional Sankey geometry/keyboard access, independent actions and stale suggestions.
- Project identities/progress; Interview attempts, answers, insights, timers, continuation and history.
- Direct entry, legacy links, refresh, back/forward, retained editors and mobile overflow.

## CI and limits

[GitHub Actions](../.github/workflows/browser-regressions.yml) installs the PDF compiler and runs backend tests, lint, typecheck, frontend helper regressions, a production build and Chromium workflows on pull requests or manual dispatch. Hosted execution is separate from local verification.

Browser tests run on the development server; the production build is checked separately. Deterministic fixtures verify behavior and contracts, not live AI quality. Physical devices, Safari/Firefox and dedicated screen-reader operation require separate checks. Timestamp-based analysis freshness is conservative and cannot certify which inputs were used.

The [portfolio capture](assets/screenshots/README.md) is an asset-production flow, not a substitute for the regression suite. Local execution logs and historical audit reports are ignored rather than published with private workspace details.

## Local acceptance — 2026-10-26

- Backend: **332 passed** after fixture logging isolation.
- Chromium desktop/mobile workflows: **148 passed**. A further **14 passed** for source/readiness/tailoring workflows after isolating fixture logs to avoid Windows file-lock conflicts.
- Frontend lint, TypeScript checking, both helper regression scripts and the production build passed. Lint still reports warnings; the backend reports a Starlette/httpx deprecation warning.
- Hosted GitHub Actions was configured but not executed as part of this local acceptance run.
