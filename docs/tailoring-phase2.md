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
- [ ] 9. Verify backend, migration/recovery, frontend and browser workflows.

Preference evaluations record their inputs and source version. Unknown evidence remains unknown; red flags never prohibit an explicit continuation. Salary comparisons use applicable annual base pay in the preference currency. Remote eligibility concerns living in NYC, regardless of the advertised remote region.

Integration checkpoint: 111 backend tests and all 20 desktop/mobile browser tests pass. Frontend typecheck passes. The first browser run caught a missing association between labels and fact controls; this was corrected and the complete suite passed. Additive migration 0005 creates intake review storage. Final production build and local migration acceptance remain pending.
