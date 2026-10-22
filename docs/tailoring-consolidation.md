# Tailoring consolidation checkpoint

Scope: repair the generation failures found in the three-role live writing evaluation, preserve historical validation and backup compatibility, and prevent cross-tab loss of unsaved resume edits. Rendering and exports remain Phase 5.

## Checkpoints

- [x] Reproduce overlap, critique-reference and split-lineage failures with fictional deterministic regressions (three failed before the fixes).
- [x] Freeze the original prompts, schemas and validation as generation v1. New snapshots explicitly select v2. Restore dispatches by the frozen snapshot version and verifies the corresponding prompt hashes; unknown versions fail closed.
- [x] Align concise composition: each overlap group can occur in only one bullet; complementary claims may share a bullet of at most 45 words. Prompts prefer individual complete claims and focused skills. Qualifiers, metrics, exclusions and source identity remain protected.
- [x] Constrain critique paths, distinguish skill references from claim references, and return precise allowed-reference errors. New split/merge bullets require accepted issue links and explicit retired parents; retained IDs cannot change their evidence identity.
- [x] Derive final content summaries from saved content rather than trusting model-written summaries.
- [x] Backend verification: 172 tests passed, including restoration of reviewed/edited v1 history alongside v2 generation. Existing Starlette/httpx deprecation warning remains. No migration is needed.
- [ ] Verify cross-tab recovery in desktop/mobile browser tests and check frontend types/build.
- [ ] Repeat the three fictional live writing samples with the unchanged approved bank; inspect writing and distinguish successful runs from diagnostics.
- [ ] Review final changes, private-data boundaries and remaining limitations.

## Compatibility and limits

`app/services/generation_v1` is a frozen compatibility implementation, not an alternative for new runs. Do not casually refactor it alongside current rules: historical validation reports, derived content, prompt hashes and approvals must remain reproducible. Manual review dispatches its validation version from the generation snapshot. Existing history stays immutable; newly generated resumes use v2.

Overlap checks enforce placement and length, not semantic nonredundancy. Prompts and human review still judge whether the source rule permits a combination and whether its wording repeats an accomplishment. Requirement mappings are model judgments, not proof of complete job coverage. Broad paraphrasing remains outside this checkpoint.

The approved private bank, job records, and pre-existing working-tree edits are preserved. Evaluation scripts, raw outputs, usage details and private reports belong under ignored storage, never in commits.
