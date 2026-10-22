# Phase 3: Resume generation

Explicit generation runs four sequential passes: select and structure, critique, revise, polish. The result is a persistent structured draft for human review. Rendering, exports, manual editing, final approval, and cover letters remain later work. Existing job analysis and selected assets remain independent.

## Step verification

- [x] 1. Baseline: 116 backend tests and frontend typecheck passed. Private v3 archive and consistent SQLite backup saved under ignored storage/backups/phase3-before. Unrelated working-tree edits preserved.
- [x] 2. Strict stage and result contracts. Separate schemas prohibit critique from returning a draft; typed bullets, requirements, evidence, decisions and edits retain stable references.
- [x] 3. Readiness and immutable eligible input snapshots. Tests cover missing/changed descriptions, revoked sources and prompt exclusion of archival, excluded, contact and template content. Older saved jobs can confirm the current description hash without recreating the job.
- [x] 4. Durable runs, attempts, revisions and compatible backups. Migration schema checks and v4 roundtrip pass; v1-v3 upgrade adapters leave generation history empty. Altered revisions fail restore validation.
- [x] 5. Bounded sequential coordinator and provider boundary. Four-call fixtures persist real stage outcomes, short transactions, fixed prompt/model versions and bounded errors.
- [x] 6. Evidence selection and structured first draft. AI/backend/full-stack fixtures preserve source records and job state. Requirements use exact posting excerpts.
- [x] 7. Critique without rewriting. Findings reference explicit fields, source IDs and requirements; draft rewriting is outside its schema.
- [x] 8. Supported revision with decision accounting. Every critique item needs a decision; new facts cannot be accepted and retained bullets cannot change evidence identity.
- [x] 9. Wording-only polish and computed differences. Only permitted source-preserving wording changes survive; the supplied edit log must equal the computed diff.
- [x] 10. Final validation, deduplication, recovery and safe retries. Concurrent starts serialize on real SQLite; duplicate request keys return the existing run. Tests cover malformed-output repair, source revocation during a provider call, expiry, late output, partial-stage reuse, and restored in-flight runs. Immutable snapshots and terminal checkpoints are enforced by SQLite triggers.
- [x] 11. Job-detail workspace and complete acceptance checks. Explicit generation, four-stage progress, history, evidence, unmet requirements and linked retries survive reloads. Existing intake checks remain visible. Desktop/mobile coverage verifies no automatic generation/analysis, preservation of job state and prior drafts, and stale-source warnings when switching history.

## Implementation boundaries

Use the activated eligible projection, full reviewed description and frozen source/settings hashes. Never send archival/excluded evidence, contact details or template placeholders to the model. Protected identity and record metadata are assembled locally. Four normal provider calls; each stage may receive one recorded repair, with 60-second attempt and 300-second run deadlines and no hidden SDK retries. Persist checkpoints without holding database transactions over provider calls. Reads never invoke generation; a failed/interrupted run requires an explicit linked retry. Uncertain provider completion cannot guarantee exactly-once billing.

Initial factual validation is deliberately conservative: complete approved claim text plus a small set of wording-only transformations. Arbitrary paraphrases, substantive deletions and unsupported combinations fail validation and may receive one recorded repair using source wording. This guards scope, negation, units and metrics without pretending lexical checks establish general semantic truth. Broader paraphrasing requires a separately evaluated semantic-review design. Human review remains mandatory, and no output is marked approved for export. Requirement coverage is the model's mapping, not proof that every requirement in the posting was found or satisfied.

Provider implementation uses the installed SDK's structured parsing and explicit refusal/incomplete handling, checked against [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs). No live provider calls were made.

## Verification and operation

- Backend: `py -3 -m pytest -q` — 146 tests passed, including three representative role families with synthetic provider outputs. Existing Starlette/httpx deprecation warning remains.
- Frontend: `npm run typecheck` and `npm run build` passed. `npx playwright test` — all 24 desktop/mobile tests passed; screenshots inspected and horizontal overflow checked. After the final intake-history display adjustment, all 10 affected intake/generation browser cases passed again.
- Local migration rehearsal preserved all 22 existing tables. A private v3 archive restored into an isolated migrated database with all 22 tables and embedded assets matching. Migration `0006_resume_generation` then applied locally after a fresh SQLite backup; all existing rows remained unchanged, all three generation tables were empty, and integrity/foreign-key checks passed. A validated v4 archive was saved.
- Recovery artifacts remain private under `backend/storage/backups/phase3-before` and `backend/storage/backups/phase3-verification`. No personal sources, generated resumes, credentials or database files are committed.

Configure `OPENAI_API_KEY` and `OPENAI_MODEL` to use explicit generation. `TAILORING_CONTEXT_TOKENS` defaults to 128000 and must fit the configured model's context window. The conservative UTF-8 byte bound reserves schema/output space and rejects oversized input instead of truncating evidence. There is no separate generation model selector.

Execution remains request-bound, without a background worker. Reloading only reads persisted progress; an interrupted process becomes retryable after its five-minute deadline. Provider timeouts and unknown completion require an explicit retry, while invalid structured output permits at most one recorded repair per stage. A successful POST can return a persisted failed run: inspect its state rather than assuming HTTP success means a completed draft.

Backup v4 validates generation history against the recorded source and currently supported prompt/validator contracts. Future prompt/schema changes must preserve a versioned validator or add an explicit backup adapter before retiring this version. Mocked tests establish flow and validation behavior; live model quality, latency, cost and rendered page fit remain unmeasured.
