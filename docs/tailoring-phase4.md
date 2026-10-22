# Phase 4: Review and editing

Scope: extend the job-detail resume workspace with edits, immutable revision history, evidence comparisons and exact-version review. Rendering, downloads, cover letters and broader semantic paraphrase approval remain later work.

## Step verification

- [x] 1. Define states/rules. Unsaved browser work is distinct from saved needs-correction, awaiting-review and reviewed versions. Source staleness is independent. Approved source metadata stays protected. Baseline: 146 backend tests passed; private v4 archive and SQLite backup saved under ignored storage/backups/phase4-before. Unrelated edits preserved.
- [ ] 2. Add revision/approval storage and compatible backups.
- [ ] 3. Implement conflict-safe, idempotent save/history/restore operations.
- [ ] 4. Validate edits and derive content, changes and unmet requirements.
- [ ] 5. Show evidence and computed baseline/parent comparisons.
- [ ] 6. Add editing and recoverable browser drafts.
- [ ] 7. Integrate generation and revision histories.
- [ ] 8. Approve an exact saved version atomically.
- [ ] 9. Handle source changes and recovery without model calls.
- [ ] 10. Complete backend/browser/build checks and commit checkpoints.

## Storage and review rules

Keep Phase 3's one immutable generated revision per run. It anchors a linear edit history with increasing sequence numbers; a restore appends another revision. A generated baseline can be reviewed directly, without a synthetic edit. Approval is a separate immutable record bound to the exact revision ID, content hash, validation hash/version and frozen input hash. New edits never inherit approval, including restorations with identical text.

SQLite write serialization and expected-current revision checks protect competing tabs. Request keys deduplicate save/restore responses. Reads never create documents or call a model. Saving structurally valid unsupported wording preserves the work as needs correction. Approval requires current sources, the current saved revision and passing server validation. Historical reviews remain inspectable after source changes.

Edits may select/order approved claims and skills and edit bullet wording. Identity, titles, employers, dates, education and section structure come from the frozen source. Employment remains reverse chronological; projects may be ordered explicitly. The existing conservative wording policy remains: unsupported paraphrases and new facts cannot be approved by checking a box. New facts require a separately approved source bundle and a new generation.
