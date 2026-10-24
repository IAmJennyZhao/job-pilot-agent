# Simple resume writing — generation v6

New resume runs use **write → advisory factual review → human review → PDF preview and approval**. This implements the direction approved after the [matched live comparison](resume-pipeline-comparison-2026-10-24.md). The previous four-pass contracts remain frozen for historical runs.

## Behavior

1. The writer receives the complete approved evidence projection and saved job description. It can paraphrase or combine compatible facts from the same record. It returns only bullet prose, record/claim references and approved skill names. Identity, education, headings, bullet IDs and skill provenance are assembled locally.
2. Structural validation rejects unavailable evidence, cross-record attribution, invalid skills and malformed output. A repairable writer failure gets one repair attempt with recorded feedback. There is no automatic retry of an uncertain provider timeout.
3. The factual reviewer receives only the written bullets and their cited facts/constraints. Each bullet gets a supported, concern or uncertain finding. These findings do not edit the draft or block it merely because a model expresses doubt. Reviewer failure, malformed findings or interruption preserve the completed writer checkpoint with review marked unavailable.
4. Local checks inspect evidence references, selected numeric boundaries and required qualifiers. A missing required internal-testing qualifier or newly invented number prevents content approval. The draft remains editable. These checks do **not** prove semantic entailment: causal links, changed attribution, technologies, metric meanings and arbitrary scope changes still require human judgment against sources.
5. Findings stay attached to the exact bullet/skill fingerprint reviewed. Editing makes them visibly stale; it never silently reruns AI. Saved history, multi-tab conflict handling, exact-content approval and export preview gates remain in effect.
6. Resume creation no longer requires quoted job requirements or a coverage map. The UI explicitly says detailed job coverage is separate; an empty requirement list is not presented as proof that every requirement is met. Optional detailed job analysis remains on the job page.

The writer targets 6–8 bullets, usually 20–35 words, with structural ceilings of 10 generated bullets and 12 skills. The estimate remains advisory; actual one-page PDF validation governs final export. No automatic layout shortening or additional rewriting pass runs.

## Recovery, storage and compatibility

- Existing run, attempt, generated revision, edit, approval and artifact tables are reused; no migration is needed. New runs freeze generation/prompt version 6 and composition version 4.
- Read-time expiration recovers a passed writer checkpoint even if review was interrupted. Recovery makes zero provider calls. Writer failures without a valid checkpoint retain bounded attempt history for an explicit retry.
- Backup validation replays writer composition, stage dependencies, advisory findings and generated content. Edited revisions retain the baseline advisory and recompute current/stale status. Backup format 7 remains sufficient; older applications that cannot validate generation 6 must reject it rather than reinterpret it.
- Generation versions 1–5 retain their prompts, validation and rendering. Their completed drafts, reviews and artifacts remain accessible. A failed historical run cannot be retried with changed policy inputs; generate a new run instead.
- New v6 render documents disable microtype protrusion. The safe-margin cutoff, fonts and margins are unchanged. Historical render documents and template bytes are unchanged.

## Verification

Automated tests use fictional model responses. They verify behavior, not live-model writing quality.

- Full backend suite: 301 tests passed before the additional SDK-boundary and minimal PDF regressions. The final focused v6 suite passed all 16 tests, including both added regressions.
- All 32 desktop/mobile browser tests passed for generation, editing, multi-tab recovery, exports and the three distinct full-workflow examples. Type checking and the production frontend build passed.
- New coverage includes faithful paraphrasing, provenance compilation at the real provider adapter, bounded writer repair, advisory concerns/timeouts/malformed responses, server-interruption recovery, blocking factual errors with editable drafts, stale advisory history, and backup round trips/tampering.
- Distinct AI, backend and full-stack acceptance fixtures use real storage, PDF compilation, preview/approval, downloads and backup restore. Historical v1–v5 backup fixtures remain in the regression suite.
- A minimal fictional PDF fixture reproduces the original line-ending margin failure and passes with protrusion disabled, using the unchanged PDF validator and identical text.

### Offline replay of the earlier live outputs

`backend/scripts/verify_simple_writer_replay.py` recompiles saved writer outputs through v6 without accessing the production database or calling a provider. On October 24, all four saved Kensho/JoinPogo full/short writer drafts passed the new local checks and rendered as valid one-page PDFs. Previously only one of these four passed the margin check. This is **offline replay**, not a fresh generation sample or a factual-quality certification.

Private results: `backend/storage/writing-evaluation/20261024T132104Z-pipeline-comparison/20261024T154538Z-v6-offline/results.json`. Original artifacts remain unchanged; no replay output is approved or inserted into production.

Reproduce from `backend`:

```powershell
py -3 scripts/verify_simple_writer_replay.py storage/writing-evaluation/20261024T132104Z-pipeline-comparison
py -3 -m pytest -q
```

Fresh live-model evaluation remains separate. The earlier four-case pilot supports this design choice but does not establish a general quality or reliability rate.
