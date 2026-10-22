# Tailoring consolidation checkpoint

Scope: repair the generation failures found in the three-role live writing evaluation, preserve historical validation and backup compatibility, and prevent cross-tab loss of unsaved resume edits. Rendering and exports remain Phase 5.

## Checkpoints

- [x] Reproduce overlap, critique-reference and split-lineage failures with fictional deterministic regressions (three failed before the fixes).
- [x] Freeze the original prompts, schemas and validation as generation v1. New snapshots explicitly select v2. Restore dispatches by the frozen snapshot version and verifies the corresponding prompt hashes; unknown versions fail closed.
- [x] Align concise composition: each overlap group can occur in only one bullet; complementary claims may share a bullet of at most 45 words. Prompts prefer individual complete claims and focused skills. Qualifiers, metrics, exclusions and source identity remain protected.
- [x] Constrain critique paths, distinguish skill references from claim references, and return precise allowed-reference errors. New split/merge bullets require accepted issue links and explicit retired parents; retained IDs cannot change their evidence identity.
- [x] Derive final content summaries from saved content rather than trusting model-written summaries.
- [x] Backend verification: 178 tests passed, including restoration of reviewed/edited v1 history alongside v2 generation, provider-plan compilation through the coordinator, and tampered-plan rejection during backup validation. After the final compact-schema constraint, all 62 affected generation/review/provider tests passed again. Existing Starlette/httpx deprecation warning remains. No migration is needed.
- [x] Verify cross-tab recovery: all 34 desktop/mobile browser tests passed, including save/discard in another tab followed by reload. Typecheck and production build passed. An earlier browser run had one Chromium `ERR_NO_BUFFER_SPACE` navigation error; the full rerun passed without changing application navigation or weakening assertions.
- [x] Repeat the three fictional live writing samples with the unchanged approved bank. Final run: all three completed all four passes on their first attempts (12 provider calls). AI/backend/full-stack took approximately 21/24/32 seconds. Longest bullets were 28/25/28 words, versus 70/47/79 in the original rejected drafts. Outputs remain unapproved private evaluation artifacts, not job records.
- [x] Review final changes and privacy boundaries. The real database and approved bank were not changed; unrelated ignore rules, mockups and architecture notes remain uncommitted. Stable backend and browser checkpoints were committed separately.

## What the live reruns changed

Prompt clarification alone did not reliably resolve the failures. The final provider protocol asks for compact claim selections rather than copied bullet text. Trusted code supplies complete source text and stable identities, combines repeated references to the same claim while retaining all requirement links, and computes unmapped requirements and final summaries. The raw plan remains in stage metadata; backup validation recompiles it and checks the saved output.

Dynamic choice slots restrict each overlap group to one representative in model-generated plans. Independent selections cannot contain those alternatives. Intersecting groups are conservatively merged. This deliberately narrower generation protocol favors focused bullets; the canonical validator also supports explicitly linked split/merge revisions and concise complementary combinations. Both retain factual and provenance checks.

Revision receives a seed that preserves independent and grouped selections. In the compact protocol each selection is a whole claim: the model cannot invent parent IDs. New selections need accepted draft recommendations; application code records authorization links. Canonical split/merge operations still require explicit retired parents and accepted issues.

Unsupported posting preferences have a separate input field so they remain visible in the final requirement map. The final samples retained the deliberately unsupported qualifications. All three polish passes returned empty edit logs: these samples demonstrate successful source-preserving composition, not broad rewriting or proven stylistic improvement from the fourth pass.

There were 65 live calls across the implementation experiments, including failed intermediate designs, followed by inspection of the final successful samples. Private results and usage are under ignored `backend/storage/writing-evaluation`; the final report is in `20261022T183446Z/REPORT.txt`. No live runs were marked reviewed, no PDF layout was claimed, and no application status changed.

## Compatibility and limits

`app/services/generation_v1` is a frozen compatibility implementation, not an alternative for new runs. Do not casually refactor it alongside current rules: historical validation reports, derived content, prompt hashes and approvals must remain reproducible. Manual review dispatches its validation version from the generation snapshot. Existing history stays immutable; newly generated resumes use v2.

Overlap checks enforce placement and length, not semantic nonredundancy. Prompts and human review still judge whether the source rule permits a combination and whether its wording repeats an accomplishment. Requirement mappings are model judgments, not proof of complete job coverage. In the final full-stack sample, a compound preferred-technology requirement remained unmet despite adjacent selected evidence; the review screen must continue to describe these as mappings rather than definitive qualification judgments. Broad paraphrasing remains outside this checkpoint.

Browser drafts now prioritize a per-tab session copy and retain a shared durable copy for reopening. Save/discard only clears a shared value that matches that tab's last persisted value. This prevents another tab's reload from losing its unsaved edits; it does not introduce a complete archive of every closed tab's unsaved versions.

The approved private bank, job records, and pre-existing working-tree edits are preserved. Evaluation scripts, raw outputs, usage details and private reports belong under ignored storage, never in commits.
