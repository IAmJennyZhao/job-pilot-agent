# Phase 4: Review and editing

Scope: extend the job-detail resume workspace with edits, immutable revision history, evidence comparisons and exact-version review. Rendering, downloads, cover letters and broader semantic paraphrase approval remain later work.

## Step verification

- [x] 1. Define states/rules. Unsaved browser work is distinct from saved needs-correction, awaiting-review and reviewed versions. Source staleness is independent. Approved source metadata stays protected. Baseline: 146 backend tests passed; private v4 archive and SQLite backup saved under ignored storage/backups/phase4-before. Unrelated edits preserved.
- [x] 2. Add revision/approval storage and compatible backups. Additive migration, schema checks, immutable history triggers, v5 roundtrip and v1-v4 adapters verified. Restoring history works with real foreign keys enabled.
- [x] 3. Implement conflict-safe, idempotent save/history/restore operations. Competing SQLite saves yield one success and one conflict; repeated request keys return the same saved revision. Restores append instead of replacing history.
- [x] 4. Validate edits and derive content, changes and unmet requirements. Tests preserve unsupported edits with blocking findings, reject protected-field input, recompute gaps and preserve the generated original and job state.
- [ ] 5. Show evidence and computed baseline/parent comparisons.
- [ ] 6. Add editing and recoverable browser drafts.
- [ ] 7. Integrate generation and revision histories.
- [x] 8. Approve an exact saved version atomically. Backend tests cover baseline/edit approval, changed content/validation/input hashes, stale revisions, duplicate review and fresh review after restore. Browser verification remains in step 10.
- [x] 9. Handle source changes and recovery without model calls. Review/edit tests run with API credentials removed and provider calls forbidden. Revoked/superseded sources and changed job text/role preserve history while blocking new review; cross-profile access is rejected.
- [ ] 10. Complete backend/browser/build checks and commit checkpoints.

## Storage and review rules

Keep Phase 3's one immutable generated revision per run. It anchors a linear edit history with increasing sequence numbers; a restore appends another revision. A generated baseline can be reviewed directly, without a synthetic edit. Approval is a separate immutable record bound to the exact revision ID, content hash, validation hash/version and frozen input hash. New edits never inherit approval, including restorations with identical text.

SQLite write serialization and expected-current revision checks protect competing tabs. Request keys deduplicate save/restore responses. Reads never create documents or call a model. Saving structurally valid unsupported wording preserves the work as needs correction. Approval requires current sources, the current saved revision and passing server validation. Historical reviews remain inspectable after source changes.

Edits may select/order approved claims and skills and edit bullet wording. Identity, titles, employers, dates, education and section structure come from the frozen source. Employment remains reverse chronological; projects may be ordered explicitly. The existing conservative wording policy remains: unsupported paraphrases and new facts cannot be approved by checking a box. New facts require a separately approved source bundle and a new generation.
