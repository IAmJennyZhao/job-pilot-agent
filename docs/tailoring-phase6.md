# Phase 6 — Cover letters

## Contract

- Independent explicit generation from the approved eligible bank and saved full posting; preference flags remain advisory.
- One immutable baseline contains 1–3 variants (default three): concise professional, technical contribution, product/user impact. Short bodies are 100–150 words; standard bodies 180–250 words.
- Existing run, stage-attempt, edit-history and exact-review tables are reused. Frozen snapshots distinguish `cover_letter` from legacy resumes. No database schema migration is needed. Backup version 7 accepts versions 1–6 and validates letter history offline.
- Writer output is sentence-structured prose. A separate assessor checks meaning against only each sentence's cited candidate claims, protected metrics, constraints, record context and exact posting excerpts. Structural checks enforce reference eligibility, numeric values/signs, technology attribution, coverage, quotes, lengths and unique IDs. The resume near-verbatim checker is never used for letters.
- Evidence assessments are model judgments, not proof of truth. Human review remains mandatory. Tests use fictional providers; no paid live writing evaluation is implied.
- Greetings, role heading and signature come from trusted saved metadata. Protected identity/employer/title/education/date labels cannot be freely authored in the body. Style-template bodies are frozen for provenance, but only paragraph/word measurements reach the writer; template personal history is never evidence. Optional company context requires an exact user-supplied excerpt, an HTTP(S) source location and explicit confirmation. It supports company facts only; no URL is fetched automatically.
- Generation permits at most one repair. Provider refusal/timeout is not silently retried. Explicit retry creates a linked run using unchanged inputs and reruns the writer/checker. Reads never invoke AI.
- Edits append immutable revisions and invalidate semantic validation. Explicit checks persist separately against exact revision/content/source hashes. Reviewed assessments are frozen. Restore creates a new unreviewed revision.
- Review covers every variant in the saved draft. This adapts the original separate-variant document proposal to the repo's existing one-baseline-per-run storage: editing any variant requires rechecking and reviewing the complete saved version. The UI explicitly asks the user to review all variants. Copy/TXT/Markdown export an individually selected variant from that exact reviewed revision, without internal evidence notes. Historical reviewed exports survive later edits/source changes; new review requires current sources.
- Existing application status, selected assets, attribution, analysis and fit scores are not mutated. Generation and checking are explicit actions. Reading, refreshing, editing, reviewing and downloading never start generation.

## Checkpoints

1. Backend contracts, shared persistence/review integration and offline archive verification: complete. Initial checkpoint committed as `e6e84be` after 205 backend tests passed.
2. Job-detail generation, sentence editing/citations, saved preview, comparisons, history/restore, review, copy and downloads: complete. Local work survives reload, lost responses, concurrent tabs and incompatible draft formats.
3. Adversarial, concurrency, compatibility and regression audit: complete. No private source assets or production database were changed during testing.

## Verification

- `py -3 -m pytest -q -p no:cacheprovider --show-capture=no --tb=short`: **216 passed**, including 23 cover-letter tests.
- `npx playwright test`: **46 passed** across desktop and mobile. The final review-confirmation change was additionally checked by rerunning all six cover-letter browser tests; all passed.
- `npm run typecheck` and `npm run build`: passed. Desktop and mobile review screenshots were inspected; horizontal overflow assertions passed.
- API tests cover count/length defaults, candidate and job citations, faithful paraphrases, unrelated valid evidence, invented history/referrals, altered scope, protected numeric signs, incomplete/forged assessments, style-only templates, confirmed company context, bounded repair, explicit retry, read-only refresh, stale sources, exact review/export hashes, and unchanged jobs.
- Recovery tests cover lost-save idempotency, failed and interrupted checks, immutable revisions, historical downloads, backup tampering and version-6 resume archives. A separate migrated SQLite test exercises concurrent checks, terminal-record update triggers, approval and a full restore/download roundtrip.
- Browser tests exercise generation, variants, optional context approval, editing, reload recovery, sentence checks, review invalidation, clipboard, TXT downloads, history restore, lost responses, incompatible drafts and concurrent tabs. Markdown/TXT content parity and escaping are checked at the API layer.

All automated generation/assessment uses fictional deterministic fixtures. These tests validate orchestration and evidence boundaries, not live-model prose quality or infallible semantic judgments. No paid live-model call was made. The existing Starlette/httpx deprecation warning remains unrelated to this change.
