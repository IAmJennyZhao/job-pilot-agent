# Phase 3: Resume generation

Explicit generation runs four sequential passes: select and structure, critique, revise, polish. The result is a persistent structured draft for human review. Rendering, exports, manual editing, final approval, and cover letters remain later work. Existing job analysis and selected assets remain independent.

## Step verification

- [x] 1. Baseline: 116 backend tests and frontend typecheck passed. Private v3 archive and consistent SQLite backup saved under ignored storage/backups/phase3-before. Unrelated working-tree edits preserved.
- [ ] 2. Strict stage and result contracts.
- [ ] 3. Readiness and immutable eligible input snapshots.
- [ ] 4. Durable runs, attempts, revisions and compatible backups.
- [ ] 5. Bounded sequential coordinator and provider boundary.
- [ ] 6. Evidence selection and structured first draft.
- [ ] 7. Critique without rewriting.
- [ ] 8. Supported revision with decision accounting.
- [ ] 9. Wording-only polish and computed differences.
- [ ] 10. Final validation, deduplication, recovery and safe retries.
- [ ] 11. Job-detail workspace and complete acceptance checks.

## Implementation boundaries

Use the activated eligible projection, full reviewed description and frozen source/settings hashes. Never send archival/excluded evidence, contact details or template placeholders to the model. Protected identity and record metadata are assembled locally. Four normal provider calls; each stage may receive one recorded repair, with 60-second attempt and 300-second run deadlines and no hidden SDK retries. Persist checkpoints without holding database transactions over provider calls. Reads never invoke generation; a failed/interrupted run requires an explicit linked retry. Uncertain provider completion cannot guarantee exactly-once billing.
