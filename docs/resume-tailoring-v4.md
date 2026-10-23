# Resume tailoring v4: polish and evidence coverage

New runs use generation/prompt/validation version 4 and composition version 2. Existing v1-v3 runs retain their original schemas, prompts, validation, reviews and backup behavior. No database migration is required. Restart the backend, refresh the job workspace and start a new generation to use v4; a retry intentionally retains its original frozen inputs.

## Changes

1. **Edit-only polish.** The model returns only `{bullet_id, replacement_text}` entries. The application copies the revised draft, validates IDs and source-preserving wording, applies changed text, and derives the ordered before/after log. Missing edits leave bullets intact. Unknown IDs, repeated IDs and factual changes fail with bounded repair; unchanged replacements are harmless no-ops. All structure, provenance, requirements, skills and coverage remain immutable during polish.
2. **Canonical requirements.** Selection returns one requirement list and one evidence assessment per requirement, independently of selected bullets. There is no separate unsupported-requirement list. Repeated descriptions and requirements written as candidate evidence gaps are rejected. Distinct qualifications may quote the same posting sentence. Claim references use schema enums drawn from approved evidence so employment-record IDs cannot be substituted for claims.
3. **Evidence-aware coverage.** Assessments distinguish full and partial claim support from the entire eligible bank. The app derives bullet links and coverage. Critique can propose structured assessment corrections; revision's accepted decisions apply those exact replacements locally. Claim evidence for stronger experience requirements remains distinct from basic skill provenance.

| Display status | Meaning |
| --- | --- |
| Supported | Selected claim evidence is assessed as full support, or a selected approved skill satisfies a basic technology qualification. |
| Partially supported | Selected evidence is assessed as partial; no selected full support is present. |
| Unsupported | No supporting claim or eligible basic-skill evidence is available in the approved bank. |
| Not included in this draft | Full or partial evidence exists, but none of that support is selected. The UI also shows its available support level. |

Basic skill matching recognizes approved catalog aliases and skill groups. A skill listing cannot establish duration, production deployment, project use or a compound requirement. Claim assessments are model judgments, not deterministic semantic proof. The compatibility field `unmet_requirement_ids` now identifies available-source gaps (partial or absent full support), rather than omitted draft content. New review UI uses the richer coverage rows and displays explanations and evidence. Historical drafts retain the old gap display.

Manual revisions recompute coverage from the saved assessments and edited content. New content receives assessment-derived links in the editor; inconsistent manually submitted links remain recoverable but cannot be approved. Review history, exact-version approval, render hashes and backup replay continue to validate the resulting content.

## Live comparison

Same saved jobs, exact short excerpts, source/projection hashes and configured `gpt-5.4-mini` model as the earlier evaluation. Production SQLite was opened read-only and copied into isolated storage; its logical digest was unchanged after every run. No live draft was approved or selected for an application.

| Case | Description | Previous v3 | Final v4 | Polish output tokens, all attempts |
| --- | --- | --- | --- | --- |
| Kensho MLOps | 51 words | Completed, 4 calls, 25.1 seconds | Completed, 4 calls, 29.3 seconds | 1,772 → 218 |
| JoinPogo Full Stack | 32 words | Failed at polish, 5 calls, 23.7 seconds | Completed, 4 calls, 16.1 seconds | 2,596 → 124 |

In this two-case sample, completion improved from 1/2 to 2/2, with no repairs in the final v4 runs. Polish output fell **92.2%** (4,368 → 342 tokens), including the old failed retry. Across all passes, total input plus output tokens fell only **3.5%** (165,239 → 159,439): richer evidence assessments add work, particularly for Kensho. Kensho became slower; the old JoinPogo duration ended in failure, so these figures are not a general successful-run speed benchmark.

Observed coverage improvements: Python is correctly supported; duplicate supported/unsupported copies are gone; basic ML/LLM evidence is recognized; Kubernetes and MCP remain unsupported; JoinPogo's professional full-stack duration is partial rather than asserted as proven. Structured critique corrections were applied to the final assessments.

Remaining quality limitations: Kensho's evaluation-pipeline requirement is still rated too generously based on output validation/testing. JoinPogo combines several capabilities into one requirement and can overstate complete production/agent coverage. Some agentic requirements are judged too conservatively. Semantic assessment and atomic requirement extraction still need human review; passing structural validation does not resolve these judgments. This change does not implement broader bullet rewriting, a hard content budget, or a production-quality benchmark.

Development used **20 live provider calls** across three two-job evaluations: 8 in the first v4 run, 4 in a follow-up that exposed shared-quote and record-ID edge cases, and 8 in the final run. Intermediate failures are preserved, not counted as final successes. Private artifacts remain ignored under `backend/storage/writing-evaluation/`, including baseline `20261022T234507Z-short-jobs`, development runs `20261023T010816Z-short-jobs` and `20261023T011218Z-short-jobs`, and final `20261023T011440Z-short-jobs` with `comparison.json`.

## Verification

- Final backend suite: **266 passed**. Frontend TypeScript check and production build passed. The broader desktop/mobile run passed **22 tests**, followed by focused coverage UI rechecks after the final handoff/display changes.
- Regression tests cover all four coverage states, source exclusions, basic versus stronger/compound qualifications, duplicate/gap requirements, shared posting sentences, record-ID rejection, edit-only polish, and mandatory application of accepted assessment corrections.
- A synthetic structured provider exercises the real compiler/coordinator, a failed polish edit and bounded repair, manual coverage recalculation, real PDF rendering, exact approval, download, backup restore and tamper rejection.
- Historical v1-v3 generation contracts and frozen backups remain tested separately from the new default.
- Desktop/mobile checks cover the generation workflow, review/history/multiple tabs, adding omitted approved content, full AI/backend/full-stack application flows, and exports. These use synthetic providers; the live evidence above is separate.
