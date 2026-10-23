# Resume tailoring v5: coverage accuracy and page budget

New runs use generation/prompt/validation version 5 and composition version 3. Historical v1-v4 runs retain their original contracts, including frozen v4 prompts. No database migration is needed. Restart the backend and start a new generation to use v5; retries retain the original snapshot/version.

## Coverage

The prompt asks for independently assessable qualifications, preserving duration, ownership and production qualifiers. A deterministic validation check rejects combinations of AI agents, backend services, APIs and web interfaces in one requirement description. Separate requirements may share a grounded sentence. Other compound qualifications rely on extraction and human review; this is not a general natural-language requirement splitter.

Approved claim assessments receive conservative source checks during selection and revision:

- Output/schema checks and ordinary testing alone cannot establish an evaluation pipeline.
- Demos, internal testing and deployment alone cannot establish production use or ownership.
- Employment dates or general software accomplishments alone cannot establish years of professional full-stack work.

Offending full-support claim links become partial links. Explanations identify these checks, and original model assessments remain in composition metadata. Accepted critique corrections pass through the same checks and cannot bypass them. Basic skill coverage remains separate from stronger experience evidence. General agent/tool understanding is not automatically treated as production-agent ownership.

These lexical safeguards address observed errors; they do not prove semantic support. They can miss paraphrases and downgrade valid evidence whose wording lacks an explicit qualifier. A downgrade retains an existing adjacent-evidence judgment, rather than proving the claim is relevant. Human review remains necessary. Thirteen authored positive/negative examples provide regression expectations, not an independently labeled accuracy benchmark.

## Content budget

Selection and revision locally rank all compiled candidates, including overlap choices, by direct requirement coverage per estimated space. Partial coverage does not eliminate the priority of direct evidence. Same-record repetition is penalized; very similar accomplishments are omitted. Skills explicitly mentioned in requirements receive priority.

The policy caps generated content at ten complete bullets and twelve skills within an estimated 670-point budget. The estimate includes header, education, skills, section headings, record headings and project overhead. It uses approximate wrapping, not font metrics. It may select fewer than six bullets when longer claims consume the space. It preserves complete approved wording, source IDs and original ordering among retained bullets. It never shrinks fonts, truncates clauses or adds facts. If even the shortest claim cannot fit the estimate, stage validation requests repair rather than silently emitting an empty resume.

Omitted claims remain in the evidence bank and coverage calculations. Available evidence absent from the draft is displayed as **Not included in this draft**, rather than unsupported. The review panel shows the saved draft's estimated budget. Manual edits may exceed the estimate; the existing real PDF preview and exact-version approval checks remain authoritative and block invalid final exports. Rendering is explicit, makes no model calls and does not silently remove more content.

## Offline comparison

Applied v5 source checks and budgeting to the exact saved final v4 Kensho/JoinPogo outputs from `20261023T011440Z-short-jobs`. Rendered both before and after through the real local PDF compiler and text/layout validator. Read only the historical isolated evaluation database; no production writes, external transmissions or new model calls occurred.

| Saved case | Bullets before / after | PDF pages before / after | Result |
| --- | --- | --- | --- |
| Kensho, 51-word excerpt | 10 / 8 | 1 / 1 | Result passes layout validation; evaluation-pipeline coverage changes from supported to partial. |
| JoinPogo, 32-word excerpt | 13 / 7 | 2 / 1 | Result passes layout validation; production-ownership coverage changes from supported to partial. |

JoinPogo's existing combined AI/backend/API/UI requirement is correctly flagged for splitting. This replay does **not** rerun extraction or demonstrate that a live model repairs it. The rendered replay is a measurement artifact, not an approved v5 generation. These two cases demonstrate local budget behavior, not general writing quality, latency or token savings. Private artifacts and the offline replay script remain ignored under `backend/storage/writing-evaluation/v5-offline-replay` and `v5-local-replay.py`.

A proposed fresh live comparison was blocked by automatic approval review because it would transmit private source/job data to an external model provider. No live v5 results are claimed; that comparison remains pending explicit approval.

## Verification

- Full backend suite at the implementation checkpoint: 285 passed. After the final ranking adjustment and two added regressions: 91 affected generation/review/export tests passed, including all 20 v5 tests.
- Synthetic structured-provider integrations exercise both v4 and v5 through real composition/coordinator logic, bounded polish repair, review/editing, local PDF exports, approval, backup restore and metadata-tamper rejection.
- Desktop/mobile acceptance: 20 passed initially; two budget-text assertions failed because the expected text omitted "the". After correcting the assertion, both affected tests passed. These browser runs use synthetic providers.
- TypeScript validation and the production build passed.

Smaller per-pass inputs, broader wording variants and optional-polish fallback are outside this change.
