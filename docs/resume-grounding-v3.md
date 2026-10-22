# Resume requirement grounding v3

The first live selection run after Phase 7 failed twice because the model attached an `Experience with:` heading to its separate list items and capitalized a sentence excerpt. All four failures were posting-quote mismatches; replaying the saved output with only those quotes corrected passed v2 validation.

New runs use generation/prompt/validation version 3. One shared posting-grounding check applies to selection, the draft being critiqued, revision, polish, final accuracy checks and manual review. It tolerates case, whitespace, list markers, and common typographic quote/dash differences. A heading may accompany an item in its actual list; it cannot be joined to unrelated text beyond a section break. Word boundaries prevent partial technology names from matching.

Revision and polish comparisons normalize quote presentation while retaining requirement IDs, descriptions, order and mappings. Candidate claims, metrics, source eligibility, lineage, skills and unmet-requirement checks retain their existing safeguards. This is deterministic excerpt grounding, not a fuzzy semantic scorer: arbitrary paraphrases and invented qualifications still require correction. Requirement descriptions can summarize the grounded excerpt. Human review remains necessary for the quality of requirement-to-experience mappings.

Versions 1 and 2 keep their existing prompt hashes and validation reports. Failed and completed old runs remain immutable, and historical reviews/exports/backups remain readable. No database migration is needed. After updating the running backend, refresh the job workspace and choose **Generate tailored resume** for v3; **Retry from saved checkpoints** intentionally requires the original unchanged snapshot and cannot upgrade a historical run.

Verification:

- The two saved failing outputs both pass a read-only v3 validator replay without changing their quotes or making model calls. Their v2 validation still reproduces the four recorded failures.
- Regression cases cover formatting, heading/list relationships, all four passes, changed technologies/numbers, unrelated headings and stable requirement mappings.
- A synthetic provider test runs through the real plan compiler and four-pass coordinator, content review, real PDF rendering, exact final approval, download and backup/restore.
- All **249 backend tests passed**, including frozen archives from versions 1–7. All **10 desktop/mobile generation and complete-workflow tests passed**, including PDF and cover-letter review/downloads.

No live model was rerun, and no user job, failed-run history or source bank was changed.
