# Phase 2: Improve Add Job

The intake flow is input, extraction (or manual entry), editable review with advisory preference flags, then an explicit decision. Unsaved previews do not create jobs. Not pursuing discards the draft; Save for later creates a Saved job; Continue to tailoring creates a Saved job and opens preparation. Detailed analysis remains a separate action. Resume generation belongs to Phase 3.

## Verification checkpoints

- [x] 1. Baseline and states: 98 backend tests and frontend typecheck pass. A private v2 archive and consistent SQLite copy are saved under ignored storage/backups/phase2-before. Existing unrelated edits are preserved.
- [ ] 2. Define evidence-backed extraction and review contracts.
- [ ] 3. Preserve full source text and bound basic extraction.
- [ ] 4. Evaluate activated preferences deterministically.
- [ ] 5. Provide editable review and accessible advisory flags.
- [ ] 6. Save atomically with retry protection, duplicate handling, migration and old-backup compatibility.
- [ ] 7. Wire the three explicit decisions.
- [ ] 8. Add a passive job-detail preparation handoff.
- [ ] 9. Verify backend, migration/recovery, frontend and browser workflows.

Preference evaluations record their inputs and source version. Unknown evidence remains unknown; red flags never prohibit an explicit continuation. Salary comparisons use applicable annual base pay in the preference currency. Remote eligibility concerns living in NYC, regardless of the advertised remote region.
