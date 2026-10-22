# Phase 2: Improve Add Job

The intake flow is input, extraction (or manual entry), editable review with advisory preference flags, then an explicit decision. Unsaved previews do not create jobs. Not pursuing discards the draft; Save for later creates a Saved job; Continue to tailoring creates a Saved job and opens preparation. Detailed analysis remains a separate action. Resume generation belongs to Phase 3.

## Verification checkpoints

- [x] 1. Baseline and states: 98 backend tests and frontend typecheck pass. A private v2 archive and consistent SQLite copy are saved under ignored storage/backups/phase2-before. Existing unrelated edits are preserved.
- [x] 2. Define evidence-backed extraction and review contracts. Typed posting/user/unknown facts distinguish mandatory/preferred years and base/total pay.
- [x] 3. Preserve full source text and bound basic extraction. Pasted text bypasses fetching, exact evidence is checked, size limits reject truncation, and basic extraction disables provider retries. Mocked extraction confirms no writes.
- [x] 4. Evaluate activated preferences deterministically. Salary boundaries, unknown evidence, NYC eligibility, direct employer and mandatory years have focused tests; missing activated preferences allows saving with checks unavailable.
- [x] 5. Provide editable review and accessible advisory flags. Basics stay compact; further details, evidence corrections and secondary checks expand. Source edits invalidate review; field corrections invalidate related evidence. Reload recomputes flags.
- [x] 6. Save atomically with retry protection, duplicate handling, migration and old-backup compatibility. A forced failure rolls back the job and status event; repeated requests return the original job. SQLite writes serialize duplicate/source checks. v3 roundtrips intake history; v1/v2 import with empty intake history. Tampered evaluation snapshots are rejected. The actual v2 backup restores in isolation; migration rehearsal preserves all 21 prior tables.
- [x] 7. Wire the three explicit decisions. Desktop/mobile tests verify no writes on discard, Saved status, duplicate links and successful retry after a lost response and reload.
- [x] 8. Add a passive job-detail preparation handoff. Current and historical flags remain distinguishable; source activation and full-description readiness are shown. Browser checks verify navigation triggers no detailed-analysis calls.
- [x] 9. Verify backend, migration/recovery, frontend and browser workflows. Final backend suite: 116 passed. All 20 desktop/mobile browser workflows passed; typecheck and production build passed. Synthetic desktop/mobile review screenshots were inspected. The real local database is at 0005, all 21 pre-existing tables are unchanged, active facts remain at 34, and the private post-migration v3 backup validates.

Preference evaluations record their inputs and source version. Unknown evidence remains unknown; red flags never prohibit an explicit continuation. Salary comparisons use applicable annual base pay in the preference currency. Remote eligibility concerns living in NYC, regardless of the advertised remote region.

The first browser run caught a missing association between labels and fact controls; this was corrected and the complete suite passed. Final input checks also cover invalid URLs, embedded URL credentials, stale review fields, a single extraction provider request and sanitized provider errors.

## Use and recovery

On `/jobs`, choose Add job, paste the link and full description, then Extract fields. Review the basics, open additional details or evidence corrections as needed, and choose Not pursuing, Save for later, or Continue to tailoring. Manual entry and URL-only extraction remain available. Preference corrections rerun deterministic checks without another AI request. Changing source inputs requires a fresh extraction or manual review; older browser drafts are retained but cannot reuse stale checks.

Continue saves once and opens the job's Tailoring preparation section. It shows the current evaluation, expandable checks recorded at save time, active-source readiness and whether the full description was reviewed. Later job edits mark old checks as historical. Detailed analysis remains an explicit action. Phase 3 will add resume generation and downloads.

Intake saves use a persisted request key and input fingerprint. A retry of the same request returns its original job, including after a lost response and reload. Changed input under an old key fails safely. Possible duplicates link to existing jobs; creating a separate posting requires an explicit checkbox. Atomic failure tests ensure neither a job nor its Saved event survives a failed review write. Intake never marks a job Applied.

Archive v3 includes reviewed inputs, evidence, decision, preference snapshot and evaluation hashes. v1 and v2 restores leave intake history empty, preserving their existing data. Review and preference snapshots are validated before restoration. Private pre-change SQLite/v2 backups, migration rehearsal, isolated v2 restore and post-migration v3 archive remain under ignored `backend/storage/backups/phase2-before/`.

## Acceptance commands

- Backend: `py -3 -m pytest -q -p no:cacheprovider` — 116 passed.
- Frontend: `npm run typecheck` and `npm run build` — passed.
- Browser: `npx playwright test` — 20 passed across desktop/mobile, using fictional sources and mocked extraction.
- Local migration: preserved all existing table rows, confirmed active eligible facts and evaluated fictional inputs against the active preference snapshot without saving a job.

No live AI calls were made during verification. Extracted classifications still require human review; exact quote matching verifies provenance, not the correctness of an interpretation. Unknown facts remain visible as checks. URL-only intake can fail on protected or oversized pages and offers pasted text/manual recovery. Resume generation is intentionally unavailable in this phase. Unrelated ignore rules, mockups and page-architecture notes were left unchanged and uncommitted.
