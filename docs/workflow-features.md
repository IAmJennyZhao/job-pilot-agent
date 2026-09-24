# Job Pilot workflow additions

## Scope

Implements the requested next steps 1, 3, 4, 5 and 6. Submitted-document snapshots (item 2) are outside this change.

| Requirement | Delivered behavior | Verification |
| --- | --- | --- |
| 1. Next actions | One action and local-calendar due date per job; edit, reschedule, complete, reopen and remove; dashboard Today, Overdue, Upcoming and Completed views | API lifecycle/validation tests; desktop and mobile job-creation/action browser flow |
| 3. Browser regressions | Repeatable Playwright suite with six workflows at desktop and mobile widths; screenshots, traces on failure, overflow checks; pull-request/manual GitHub workflow | 12 local browser tests passed against disposable synthetic servers |
| 4. Interview practice | Per-answer timer with pause/reset and target; timer and draft survive reload; exact answers, elapsed time and feedback retained for each attempt; earlier/latest comparison and revision; access from session history | API tests for exact answer/score pairing, timing and session membership; browser evaluates two revisions, compares and reloads |
| 5. Outcome reporting | Outcomes page groups by source, role category or recorded resume version; applied/interview/offer counts and rates, sample sizes, saved-since cohort, contributing job links | Reporting API tests cover archived outcomes, inferred stages, denominator, date range, immutable labels and unknown history; browser grouping/date checks |
| 6. Export and backups | Jobs CSV; full JSON archive with all database tables and available resume PDFs; validated preview; explicit replace confirmation; recovery archive before restore and downloadable recovery history | Round-trip data/PDF tests, invalid references/paths/types/hash/confirmation rejection, CSV formula escaping, missing-PDF disclosure, transaction rollback; desktop/mobile download-preview-restore flow |

## Product details

- Action dates use the browser's local calendar date. The agenda intentionally includes closed and archived jobs, since feedback and other follow-ups can still be useful. Its scope is independent of the dashboard analytics date cohort.
- Interview timers measure an answer, keep running through refreshes until paused, and never submit automatically. Each scored attempt retains its exact answer alongside feedback to avoid timestamp ambiguity. Older feedback without an exact answer snapshot uses the existing historical pairing fallback. Scores remain AI coaching estimates.
- Source/category/resume-version labels are frozen when progress beyond Saved is first recorded. The version fingerprint describes the selected resume content at that time; it is not proof that the resume was submitted. Historical jobs without recorded attribution are explicitly unknown for resume version. Their source/category use current details. Reporting includes archived jobs and infers earlier stages from later progression.
- Full backups include persisted application assets, jobs, analyses, status history, actions, interview questions/messages/feedback, study progress, skills and attribution. They exclude API keys, app configuration and unsaved browser drafts. Archives must match the supported format/schema and stay within 50 MB. Missing original PDFs are disclosed; their stored text and records remain included.
- Restore validates data in a disposable database before replacement. Imported file paths are rejected; PDFs are staged under fresh generated names. Database replacement is transactional. Existing files are retained so the recovery archive can restore the previous state. Close other app tabs before restoring. The restoring browser clears its old drafts and cached records.
- Recovery archives are stored below the configured asset storage directory, in `backups`. The Data page lists them after a reload. Download one and use the same preview/restore flow to recover it.
- Migrations add only the action and attribution tables. Legacy databases now adopt the baseline revision and run subsequent migrations rather than incorrectly stamping the latest revision without applying changes.

## Run checks locally

From `backend`:

```powershell
py -3.13 -m pytest -q -p no:cacheprovider
```

From `frontend`:

```powershell
npm ci
npx playwright install chromium
npm run test:browser
npm run typecheck
node tests/list-editing.cjs
node tests/form-validation.cjs
npm run build
```

The browser runner starts its own frontend on port 3100 and synthetic backend on port 8100. It refuses to reuse existing servers, creates a fresh database and asset directory under temporary storage, and stubs AI responses. It never opens the real database or calls external AI services. On Linux use Python 3.13 and install Chromium dependencies with `npx playwright install --with-deps chromium`.

The GitHub workflow runs this same browser command on pull requests or manual dispatch after these commits are pushed. Its hosted execution has not been triggered from this task. Local verification covers Chromium at 1440×1000 and 390×844; it does not claim Safari/Firefox or live AI evaluation quality.

## Final verification

- 66 backend tests passed.
- 12 desktop/mobile browser tests passed, including all six workflows and document overflow assertions.
- TypeScript and both existing frontend regression scripts passed.
- Production build passed, including the new Outcomes and Export & backups pages.
- The user's database was not used for mutations or restore testing. The pre-existing root `.gitignore` edit remains outside these commits.
