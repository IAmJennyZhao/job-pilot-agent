# Phase 6 — Cover letters

## Contract

- Independent explicit generation from the approved eligible bank and saved full posting; preference flags remain advisory.
- One immutable baseline contains 1–3 variants (default three): concise professional, technical contribution, product/user impact. Short bodies are 100–150 words; standard bodies 180–250 words.
- Existing run, stage-attempt, edit-history and exact-review tables are reused. Frozen snapshots distinguish `cover_letter` from legacy resumes. No database schema migration is needed. Backup version 7 accepts versions 1–6 and validates letter history offline.
- Writer output is sentence-structured prose. A separate assessor checks meaning against only each sentence's cited candidate claims, constraints, record context and exact posting excerpts. Structural checks enforce reference eligibility, numeric values, technology attribution, coverage, quotes, lengths and unique IDs. The resume near-verbatim checker is never used for letters.
- Evidence assessments are model judgments, not proof of truth. Human review remains mandatory. Tests use fictional providers; no paid live writing evaluation is implied.
- Greetings, role heading and signature come from trusted saved metadata. Style-template bodies are frozen for provenance, but only paragraph/word measurements reach the writer; template personal history is never evidence. Company context comes from the saved posting; no automatic research.
- Generation permits at most one repair. Provider refusal/timeout is not silently retried. Explicit retry creates a linked run using unchanged inputs and reruns the writer/checker. Reads never invoke AI.
- Edits append immutable revisions and invalidate semantic validation. Explicit checks persist separately against exact revision/content/source hashes. Reviewed assessments are frozen. Restore creates a new unreviewed revision.
- Review covers every variant in the saved draft. Copy/TXT/Markdown export an individually selected variant from that exact reviewed revision, without internal evidence notes. Historical reviewed exports survive later edits/source changes; new review requires current sources.

## Checkpoints

1. Backend contracts, shared persistence/review integration and offline archive verification: implemented. Full backend suite: 205 passed.
2. Review/edit interface, recovery and functional browser tests: in progress.
3. Final adversarial, concurrency, compatibility and regression audit: pending.
