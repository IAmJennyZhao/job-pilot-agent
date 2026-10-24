# Resume pipeline comparison — October 24, 2026

The simple writer is the strongest candidate for the next implementation experiment. It produced all four drafts much faster and with fewer tokens, and preserved an important source qualifier that the current pipeline omitted. The factual reviewer did not demonstrate a confirmed factual correction in this pilot and raised a clear false alarm. Keep factual findings visible, but do not equate a model verdict with truth or make every advisory finding a generation failure.

This is a four-case pilot using **two jobs**, not four independent jobs or a production reliability benchmark. No production application code was changed.

## Method

- Same `gpt-5.4-mini` model, approved source projection, job text per case, identity/education/record metadata, and owned PDF renderer across arms.
- Kensho: the existing 51-word excerpt and the full 1,277-word posting. JoinPogo: the existing 32-word excerpt and the full 552-word posting. Full postings were used as saved, including scraper/page boilerplate.
- **Current:** real v5 four-pass coordinator, existing validation, local content budget and bounded repair.
- **Writer:** one call returning bullet prose, record/evidence references, and approved skill names. Faithful rewriting and combining compatible facts are allowed. Local checks verify record attribution, evidence references and skill eligibility; they do not certify semantic support.
- **Writer + reviewer:** the exact same writer draft, followed by a factual review using only each bullet and its cited facts/constraints. One targeted repair and recheck are allowed. The draft survives advisory review failure.
- No automatic layout repair, silent truncation, extra retries or replacement runs. All original failures are retained. All arms use the same renderer; the current arm has its existing enforced space estimate, while the experimental writer has only a short content-budget prompt.
- One sample per case, sequential execution in fixed order. Identical source/projection hashes were recorded. The full bank was supplied to both current selection and the writer; only review context was narrowed. No model upgrade, retrieval system or user preference labels were introduced.
- **24 actual provider calls**, below the approved 48-call cap. Reviewer-arm totals include the shared writer call when estimating the cost of that standalone pipeline; it was not billed twice. All drafts remain unapproved evaluation artifacts.

The production database was read-only and copied into private evaluation storage. Its logical digest was unchanged after the run. The harness dry run also made zero provider calls and left production unchanged.

## Results

Times are measured generation/coordinator times, excluding PDF rendering. Token counts are input plus output, not dollar estimates.

| Case | Current: state / seconds / tokens | Writer: seconds / tokens | Writer + reviewer: seconds / tokens | Reviewer result |
| --- | --- | --- | --- | --- |
| Kensho short | Completed / 22.335 / 83,897 | 3.107 / 15,045 | 13.181 / 27,811 | Two initial flags; repair/recheck still leaves two flags. Draft preserved. |
| Kensho full | Completed / 23.035 / 96,733 | 2.917 / 16,721 | 5.221 / 20,590 | No flags; unchanged draft. |
| JoinPogo short | Completed / 18.816 / 78,328 | 2.875 / 15,027 | 5.463 / 19,260 | No flags; unchanged draft. |
| JoinPogo full | Failed / 15.580 / 40,352 | 3.136 / 15,702 | 5.576 / 19,892 | No flags; unchanged draft. |

Current generation completed **3/4**, while the simple writer produced **4/4** drafts. Reviewed drafts were preserved in **4/4**, but only **3/4** received an all-supported model verdict. These are different success criteria: draft creation, automated factual clearance and export eligibility must not be conflated.

Median current time among its three successful cases was **22.335 seconds**. Writer median across all four was **3.012 seconds**, and writer-plus-reviewer median was **5.520 seconds**. On the three matched cases where current generation completed, writer used **81.9% fewer tokens** and writer-plus-reviewer used **73.9% fewer tokens**. Latency is a single-run observation, not a stable benchmark; the failed current full-JoinPogo run also received cached input tokens, unlike the other calls.

## What failed

### Current: requirement quotation prevents a draft

Full JoinPogo failed selection twice. The saved posting says, “Design, build, and implement AI agents, backend services, APIs and web UIs.” The model split it into independent requirements, but used reconstructed quotes such as “Design, build, and implement backend services.” Those reconstructed excerpts fail the current grounding rule. The repair repeated the same quotes.

The qualifications are substantively present in the posting, but the quote representation cannot pass validation. This is another example of analysis metadata preventing resume creation. It is a different failure from the previous Kensho critique-reference error. The previous failed runs remain documented in `resume-tailoring-v5.md`; this run does not replace them.

### Current: preserved source wording still loses a required qualifier

All three completed current drafts select CCHC-09, whose approved text describes contributing to a Dockerized dementia-care backend. Its separate constraint explicitly requires preserving internal-testing status. None of those three current drafts includes that status. Full Kensho also selects CCHC-08, which carries the same scope constraint.

All four writer drafts explicitly say **internal-testing** and retain team contribution. This was verified against the saved draft text and claim constraints. It shows why copying approved sentences is insufficient when important qualifications live outside the sentence itself. This is an assistant source audit, not an independent human evaluation or a claim that every generated clause has been proven correct.

### Reviewer: false alarms and inconsistent judgments

On short Kensho, the first review says bullet 5 omits internal-testing scope. The original bullet already says “an internal-testing dementia-care app.” The repair returns exactly the same text for that bullet. This is a clear false positive.

The review also objects to the AI4DQ bullet's shortened wording about summaries, limitations and next checks. Repair expands it toward source wording; recheck then objects to combining the related evidence. Recheck additionally flags an unchanged data-quality bullet that the first review accepted. Some concerns about combining facts warrant judgment, but the literal missing-qualifier allegation is demonstrably incorrect. The resulting draft remains available with two advisory findings instead of disappearing.

The other three reviewed drafts are identical to their writer drafts. No confirmed factual correction by the reviewer was established in this pilot. This does not demonstrate that review is unnecessary in general; it demonstrates that this reviewer prompt/model is not yet a calibrated release gate.

## Rendering

All **11 produced variants** rendered to one page, including duplicated unchanged reviewed drafts. The three completed current drafts passed the existing PDF validator. Only short Kensho passed for the experimental arms; the other three writer drafts and their unchanged reviewed versions failed the margin check.

Inspection localized every experimental margin finding to a line-ending span whose right edge was **571.115–571.184 points**, versus the validator's **571-point** cutoff. Examples include the final words “S3.”, “repeatability.” and “clarity.” These are approximately **0.115–0.184 point** excesses, not second-page overflow or missing text. PDF text-order/content checks passed; sampled page images, including all three experimental failure cases, showed no visible clipping.

This looks consistent with a typography/bounding-box tolerance issue, possibly involving the template's microtype protrusion, rather than excessive resume length. The specific renderer cause was not proven. The validator was **not** relaxed, and all six failing artifacts remain formally invalid. A production change should reproduce this with a small fixture and preserve meaningful clipping checks before adjusting the template or tolerance.

## Writing assessment

My qualitative preference is the writer drafts as a starting point, particularly for full-stack roles. This is not a blinded assessment and the user has not yet supplied preference labels.

- The writer combines related pipeline accomplishments and their outcomes into cohesive bullets, instead of allocating separate bullets to pipeline automation and failure recovery.
- The writer represents distinct project functions more clearly. The current short-JoinPogo result includes two similar JobPilot overview bullets; the writer uses an overview plus a concrete extraction/validation accomplishment.
- The writer preserves useful context such as internal-testing, local use, read-only investigation and public-demo scope.
- It is **not uniformly more concise**: writer bullets average roughly 26–28 words versus 19–20 for completed current drafts. Some bullets contain long technology lists already repeated in project headings; those would benefit from editing.
- Selection still needs judgment. The short-Kensho writer omits AWS from its skill list despite an AWS claim in its experience; the current draft includes it. No independent coverage study was performed, and broader rewriting is not proof of better relevance in every case.
- Factual and writing judgments should remain separate. The audit found the qualifier omission above and a clear reviewer false alarm; it did not establish a comprehensive hallucination rate for any arm.

## Recommended direction

Prototype a simple writer with source references, local identity/evidence checks, and explicit required-qualifier checks. Retain draft history and rendering safeguards. Keep factual-review findings advisory for uncertain judgments while retaining approval blocks for confirmed contradictions, missing mandatory qualifiers and invalid artifacts. Preserve every draft and make any needed corrections reviewable.

Before replacing the production path: add the missing-qualifier example and reviewer false-positive example to an evaluation set; investigate the tiny margin failures separately; obtain the user's preference on the private review packet; and repeat on more genuinely different jobs. Keep requirement coverage separate from draft creation. The current four-pass pipeline is still installed.

## Reproduction and artifacts

- Harness: `backend/scripts/compare_resume_pipelines.py`; default invocation is dry-run, `--live` makes explicitly authorized provider calls. Model is pinned to `gpt-5.4-mini` for this comparison.
- Offline measurement and packet generation: `backend/scripts/summarize_resume_comparison.py <evaluation-directory>`.
- Private live root: `backend/storage/writing-evaluation/20261024T132104Z-pipeline-comparison`.
- `protocol.json`, per-case snapshots, complete provider inputs/outputs/usage, current coordinator runs, `results.json`, `measurements.json`, `integrity.json`, and `review-packet.md` are preserved there. Each generated arm has PDF/TeX/text, structured content, page images and the unmodified layout verdict.
- Preparation dry-run: `20261023T190926Z-pipeline-comparison`. Earlier preparation attempt `20261023T190847Z-pipeline-comparison` stopped on an isolated pending-run conflict; zero provider calls occurred, the harness was corrected, and the subsequent dry-run passed all four cases.
- The private artifacts are ignored by Git. Only the experiment scripts and this report are committed. Unrelated user files were left untouched.
