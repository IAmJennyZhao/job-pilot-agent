# Phase 4: Review and editing

Scope: extend the job-detail resume workspace with edits, immutable revision history, evidence comparisons and exact-version review. Rendering, downloads, cover letters and broader semantic paraphrase approval remain later work.

## Step verification

- [x] 1. Define states/rules. Unsaved browser work is distinct from saved needs-correction, awaiting-review and reviewed versions. Source staleness is independent. Approved source metadata stays protected. Baseline: 146 backend tests passed; private v4 archive and SQLite backup saved under ignored storage/backups/phase4-before. Unrelated edits preserved.
- [x] 2. Add revision/approval storage and compatible backups. Additive migration, schema checks, immutable history triggers, v5 roundtrip and v1-v4 adapters verified. Restoring history works with real foreign keys enabled.
- [x] 3. Implement conflict-safe, idempotent save/history/restore operations. Competing SQLite saves yield one success and one conflict; repeated request keys return the same saved revision. Restores append instead of replacing history.
- [x] 4. Validate edits and derive content, changes and unmet requirements. Tests preserve unsupported edits with blocking findings, reject protected-field input, recompute gaps and preserve the generated original and job state.
- [x] 5. Show evidence and computed baseline/parent comparisons. The selected revision has evidence text/constraints, gaps, validation findings and before/after comparisons against the generated draft, previous revision or approved source wording.
- [x] 6. Add editing and recoverable browser drafts. Desktop/mobile tests cover reload recovery, removal/reselection of approved claims and skills, discard, unsupported wording, stale-parent conflicts, explicit comparison before carrying edits forward and retry after a lost save response.
- [x] 7. Integrate generation and revision histories. Generation attempts retain their original output; manual history selects, compares and restores revisions. Historical approvals remain visible. Existing generation/retry browser tests pass with the review workspace integrated.
- [x] 8. Approve an exact saved version atomically. Backend tests cover baseline/edit approval, changed content/validation/input hashes, stale revisions, duplicate review and fresh review after restore. Browser verification remains in step 10.
- [x] 9. Handle source changes and recovery without model calls. Review/edit tests run with API credentials removed and provider calls forbidden. Revoked/superseded sources and changed job text/role preserve history while blocking new review; cross-profile access is rejected.
- [x] 10. Complete backend/browser/build checks and commit checkpoints. All 165 backend tests and 32 desktop/mobile browser tests passed. Typecheck and production build passed; the final editor/review flow passed again on both viewports after timestamp display was added. Editor/comparison screenshots were inspected. Stable baseline, backend, provenance and UI checkpoints were committed.

## Storage and review rules

Keep Phase 3's one immutable generated revision per run. It anchors a linear edit history with increasing sequence numbers; a restore appends another revision. A generated baseline can be reviewed directly, without a synthetic edit. Approval is a separate immutable record bound to the exact revision ID, content hash, validation hash/version and frozen input hash. New edits never inherit approval, including restorations with identical text.

SQLite write serialization and expected-current revision checks protect competing tabs. Request keys deduplicate save/restore responses. Reads never create documents or call a model. Saving structurally valid unsupported wording preserves the work as needs correction. Approval requires current sources, the current saved revision and passing server validation. Historical reviews remain inspectable after source changes.

Edits may select/order approved claims and skills and edit bullet wording. Identity, titles, employers, dates, education and section structure come from the frozen source. Employment remains reverse chronological; projects may be ordered explicitly. The existing conservative wording policy remains: unsupported paraphrases and new facts cannot be approved by checking a box. New facts require a separately approved source bundle and a new generation.

Bullet IDs retain their first evidence identity across the entire revision chain, including removed bullets. Invalid edits cannot redefine provenance by being saved twice. Restoring the original source identity remains valid. Validation for manual edits is independent of the AI critique decision log; all derived text, gaps and comparisons come from saved structured content.

## Verification and operating notes

- Backend: 165 tests passed, including 19 Phase 4 cases. Existing Starlette/httpx deprecation warning remains. Tests prohibit model calls during editing/review and remove API credentials.
- Browser: all 32 desktop/mobile tests passed. This includes reload/discard, invalid edits, exact review and re-review, restoration, concurrent tabs, explicit conflict resolution, source staleness and a lost save response without a duplicate revision. Horizontal overflow checks passed.
- Frontend: `npm run typecheck` and `npm run build` passed. Desktop/mobile editor and comparison screenshots were inspected. Generation in tests used synthetic provider fixtures; no paid model calls or approvals of the owner's real resume were performed.
- Migration `0007_resume_review` was rehearsed on a database copy, then applied locally after a fresh SQLite backup. All 25 existing tables were unchanged; two new review tables were added. Integrity and foreign-key checks passed. A private v4 archive restored into an isolated migrated database with all 25 original tables and embedded assets matching. A validated v5 archive was saved.
- Private recovery artifacts live under ignored `backend/storage/backups/phase4-before` and `backend/storage/backups/phase4-verification`. Personal sources, databases, generated documents and credentials are not committed.

Each generated baseline has its own current manual revision. An older generation can still retain a reviewed version; choosing another generation never transfers that approval. Source eligibility is computed separately from historical review. Approval can be recorded only for the current revision of that baseline, with current matching sources and passing validation.

Browser drafts preserve their baseline/profile and expected parent IDs. A server conflict keeps local content available for comparison; carrying it onto the newest revision is an explicit action bound to the compared version. It does not automatically merge competing edits. Save and restore request identities survive reloads. No extra confirmation dialog is needed for Mark reviewed: that button is the explicit content approval action.

Backup v5 checks revision ancestry, restore provenance, request identities, derived content and exact approval hashes before restoring. Legacy archives do not acquire review approval. Future changes to review validation must retain a versioned validator or introduce a backup adapter; never silently reinterpret approved history.
