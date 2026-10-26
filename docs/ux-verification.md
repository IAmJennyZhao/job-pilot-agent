# UI/UX audit verification

Scope: the original 32 findings, the subsequent 30-point review, and regressions found while exercising the fixes. Verification uses the production Next.js build and a synthetic database. No production records were changed.

## Automated checks

- `cd backend; py -3.13 -m pytest -q -p no:cacheprovider`: 56 passing tests, including migration tests.
- `cd frontend; npm run typecheck`: passing.
- `cd frontend; npm run build`: passing.
- `git diff --check`: passing.
- New API regressions cover every funnel node/branch, stage regressions, additional filters, invalid transitions, active/closed scope, coverage drill-downs, skill evidence links, saved study progress and timezone-aware timestamps.

## Original findings

| # | Issue resolved | Implementation and verification |
|---|---|---|
| 1 | Funnel counts differed from click results | Dedicated cumulative-stage filters; API test compares every node count with its returned jobs. Browser confirmed the one-job rejection cohort. |
| 2 | Branch clicks lost the source stage | Source and destination travel together in the URL and visible filter summary; tests compare every branch count. |
| 3 | Overlapping chart paths | Replaced overlapping curves with stage bars and explicit outcome branches, showing counts and percentages directly. Visually checked desktop and mobile. |
| 4 | Fixed-width chart | Responsive stage cards and outcome lists; mobile dashboard has no document overflow at 390px. |
| 5 | Withdrawn jobs counted as active | Active uses open-opportunity rules; automated test checks the metric and matching list. |
| 6 | Truncated previews lacked complete lists | Stale, analysis, missing-pay, missing-fit and low-confidence sections have View all links with dedicated filters. Coverage scope is regression-tested. |
| 7 | Search Health incorrectly said Clean | Attention state considers stale jobs, missing data and missing analysis. Synthetic dashboard with fresh but incomplete jobs shows Needs attention. |
| 8 | Intake squeezed the tracker | Intake is collapsible; desktop table uses the available width and mobile uses job cards. Both layouts inspected. |
| 9 | Filters lost on refresh/navigation | URL-backed filters and explicit return links. Browser checked status + search through refresh, job detail and Back to jobs. |
| 10 | No clear filter context/reset | Removable filter chips, source-to-outcome summary and Clear all. Browser exercised removal and clearing. |
| 11 | Inline save errors were invisible | Mutation errors are displayed, saves are locked while pending, and pay editor retains input after failure. Browser submitted negative pay, saw field-specific error, corrected it and saved successfully. |
| 12 | Show hidden was unclear | Checkbox explicitly names archived, rejected and ghosted records; funnel exclusion of archived records is shown separately. |
| 13 | No sorting | Recently updated, company A–Z and highest annual pay controls. Sorting applies to the complete filtered collection. |
| 14 | Full detail required a preview step | Role links open details directly; Preview is a separate action. Browser verified direct navigation and return context. |
| 15 | Simulated extraction progress | Removed timer-driven claims; extraction and analysis show honest pending messages. |
| 16 | Creation lacked a clear destination | Success message links to the saved job, even if filters hide it. Browser created a synthetic job and verified its direct link. |
| 17 | Detail hierarchy was hard to scan | Section navigation links only to available role, fit, company, prep, assets and history sections. Verified tracker-only details do not link to missing analysis sections. |
| 18 | JSON editing and silent invalid-data fallback | Experience, projects and education use recursive structured editors that preserve existing keys. Invalid legacy drafts block saving with an explicit error. Browser edited structured experience fields. |
| 19 | Ready/merge used older saved values | Editor actions await saving before confirming/merging. Collapsed cards with pending drafts require editing first. Browser verified edited title on Ready and edited skills in the merged base profile. |
| 20 | Unsaved asset edits disappeared | Per-record session drafts for base profile, variants and letters; also applied to intake, job edits and interview answers. Browser verified tab switches, refresh and isolation between two jobs. |
| 21 | Readiness badges were inert/misleading while loading | Checks link to the correct asset tab and render only after all asset queries succeed. Browser exercised profile/resume tabs and readiness changes. |
| 22 | Answers leaked between questions | Answer drafts keyed by session and question; switching questions is locked during evaluation. Browser verified independent Q1/Q2 text. |
| 23 | Interview draft recovery missing | Active set, questions and answer drafts persist in the browser tab; browser verified both answers after reload. New practice does not erase drafts belonging to older sessions. |
| 24 | Interview loading/errors were incomplete | Job choices, history, insights, resume and session detail have explicit loading/error states; unavailable data is not presented as empty results. Missing-session errors are visible and have a route back to the saved draft. |
| 25 | Skill evidence was inaccessible | Each skill opens matching resume/job/interview sources. Historical counts are labeled Mentions, not jobs. Browser opened LangChain evidence; API test verifies its job link. |
| 26 | Plan deletion/rename feedback missing | Delete requires confirmation; rename has explicit Save/Cancel and both operations display failures. Reviewed handlers and rendered controls. |
| 27 | Study plans could not track progress | Saved task and project checkboxes update persisted completion and progress. Browser and API test verified completion after reload; API test verifies rename preserves progress. |
| 28 | Profile prerequisite unexplained | Generation shows loading/error or a link to create the required base profile. Conditional states checked in implementation and initial loading UI. |
| 29 | Preview lacked dialog behavior | Native modal dialog provides focus containment, Escape and focus restoration. Browser confirmed Escape returned focus to Preview and to the skill evidence trigger. |
| 30 | Controls lacked accessible names | Filters, row editors, links, history inputs, upload and time-budget controls have explicit names. Verified accessible browser trees. |
| 31 | Mobile navigation had icons only | Visible labels, active-page semantics and skip link. Visually checked at 390px. |
| 32 | Funnel lacked an accessible equivalent | Semantic lists, descriptive links, direct counts/percentages and a transition table replace the SVG-only presentation. Browser accessibility tree exposes each population. |

## Additional findings fixed during verification

- API datetime fields now declare UTC, preventing SQLite timestamps from appearing hours late. Regression test plus browser verification: a synthetic record displayed 2:20 PM after normalization instead of 6:20 PM.
- Draft identities cannot leak from one job/asset into another. Browser verified a draft in Applied did not appear in Saved, then recovered it on return.
- Explicit interview targets and missing/resuming sessions cannot silently display a different recovered practice set. Starting another session has an explicit new-session intent.
- Save-dependent editors lock input while requests are pending, so a successful earlier request cannot discard text typed during that save.
- Status-history editing no longer uses fixed columns wider than its sidebar; history controls are labeled and deletion explains its effect on current status/history.
- Validation responses name the failed fields. Pay-error recovery was exercised end to end.

## Repeatable browser verification

`cd backend; py tests/ux_fixture.py` starts a fresh temporary synthetic database on port 8000. It does not read or overwrite the normal database. Start the built frontend with `npm run start` from `frontend`. The fixture includes synthetic jobs, two resumes, a cover letter, skill evidence, a study plan and interview questions. Its AI outputs are fixtures rather than live model calls.

Desktop and 390px mobile views were checked for the dashboard, tracker, assets, skills and interview practice. Existing broad skill tables retain horizontal scrolling inside their panel; the document itself does not overflow. External AI quality and third-party job-posting availability are outside this UI verification; their loading and error paths remain explicit.

## Follow-up review: checkpoint 1

The subsequent 30-point review adds scope beyond the original audit. The following final checklist records the completed follow-up.

Verified in this checkpoint:
- Funnel cohort heading and archived exclusion replace the contradictory hidden-record checkbox. Synthetic rejection-after-Tech drill-down shows exactly one matching job.
- Clear filters preserves sorting (browser URL remains `?sort=company`). Search is debounced and retains visible results while loading.
- Laptop tracker uses cards with category editing and posting links. Screenshots at 1280px and 390px show no document overflow.
- Row pending state uses mutation identities; compensation has an explicit edit affordance and salary sorting groups currencies.
- Responsibilities, skills and benefits use item editors. Profile lists use one item per line. `node frontend/tests/list-editing.cjs` reproduces the old comma split and passes with the new parser.
- Browser drafts survive closing the tab: a synthetic profile draft reopened with the exact edited name. Readiness Skills focuses its field. Asset tabs persist in the URL.
- Readiness requires content, interview generation locks setup, job selection supports search and active/closed groups, and mode buttons announce selection.
- Skills errors suppress false empty states; optional project completion is separate from required study tasks. Dates include years.
- Missing-session browser check shows an error and recovery link without unrelated question/answer UI.
- Production build and frontend typecheck pass.

The remaining dashboard, validation and recovery work was completed in the final checkpoint below.

## Follow-up review: final checklist

| # | Requirement | Final behavior and evidence |
|---|---|---|
| 1 | Historical filter context | Cohort heading distinguishes reaching a stage from current status. Browser rejection-after-Tech example returns one job. |
| 2 | Consistent archived scope | Funnel mode replaces the hidden-record checkbox with an explicit historical-scope explanation; archived jobs stay excluded. |
| 3 | Stage conversion | Every stage shows conversion from its predecessor as well as share of total. Browser verified 75% Applied-to-Recruiter in the synthetic cohort. |
| 4 | Recorded versus inferred | API counts explicit history/current status separately. Regression test covers a directly created Tech Screen job with inferred Recruiter Screen. Both values appear in the visual card and accessible link name. |
| 5 | Timeframe selection | All-time, last-30/90-day shortcuts and an absolute saved-since date. Dashboard and job APIs share the saved-date boundary. API regression verifies old jobs are excluded; browser verifies date survives a branch drill-down. |
| 6 | Prioritized action queue | One deduplicated queue of up to five jobs; stale, analysis, then missing-data priority. Coverage details are collapsed. Browser inspected the queue and its links. |
| 7 | Laptop tracker layout | Cards remain in use below the wide-desktop breakpoint; checked at 1280px and 390px with no document overflow. |
| 8 | Search behavior | 250ms debounce, previous results retained with visible updating status, URL remains authoritative. Source checked alongside browser filter navigation. |
| 9 | Pending row scope | Mutation identities disable the affected row, including compensation. Delayed fixture showed the changed row disabled and a different row enabled. |
| 10 | Mobile quick actions | Category editor and source link included in each card; visible in browser and responsive screenshots. |
| 11 | Compensation affordance | Explicit Edit compensation text; browser opened the editor through this action. |
| 12 | Currency-safe sorting | Salaries sort within currency groups; UI explains that exchange-rate conversion is not performed. Comparator and labels inspected. |
| 13 | Clear filters preserves sort | Browser verified the resulting URL remains `?sort=company`. |
| 14 | List item integrity | Explicit item controls for job responsibilities/skills/benefits, newline-only profile lists, multiline target roles. Regression test preserves punctuation; browser saved and reloaded “Design, build, and test APIs” as one item. |
| 15 | Inline validation | Negative amounts, reversed ranges and malformed posting URLs show field errors and disable saving. Tests cover boundary values and protocols. Browser verified invalid amount and URL states; correction re-enables save. |
| 16 | Analysis recovery guidance | Pending UI explains keeping the page open, retained saved jobs/source drafts and retry/manual-entry recovery. No simulated progress or unsupported cancellation claims. |
| 17 | Consistent confirmations | Shared native modal for archive/delete/discard/replace actions. Browser verified cancelling preserves the draft and restores focus to the trigger. |
| 18 | Content-based readiness | Requires actual profile/resume/template content. Browser saved whitespace-only synthetic letter and saw “Needs assets” with the missing requirement; restored content afterward. Letter body is directly visible in the editor. |
| 19 | Durable drafts | Browser-local persistence with migration from existing session drafts. Browser closed/reopened a tab and recovered exact content. Asset editors also offer confirmed Discard draft; browser verified saved profile restored after discard and reload. |
| 20 | Shareable asset tabs | URL-backed tab selection, verified through navigation and reload. |
| 21 | Readiness navigation | Readiness selects the correct tab and scrolls/focuses the field or section. Browser verified Skills focus before and after field-label changes. |
| 22 | Generation target locking | Disabled setup fieldset while generation runs. Delayed fixture confirmed role/stage controls disabled, followed by usable generated practice. |
| 23 | Searchable saved-job choices | Search by company/role, active versus closed groups, selected job retained. Loaded option grouping and implementation inspected. |
| 24 | Interview mode state | Saved job / General role buttons use aria-pressed; confirmed in the accessibility tree. |
| 25 | Error versus empty states | Skills loading error suppresses No gaps yet and supplies Retry. Conditional rendering checked. |
| 26 | Unique-job skill priority | API and study-plan input prioritize current unique active jobs, retaining historical mentions separately. Repeated-analysis regression and manual-requirement evidence regression pass; browser shows both counts. |
| 27 | Optional projects | Study-task and optional-project completion are separate. Browser completed a project and verified required-task progress stayed at 1 of 2. |
| 28 | Consistent query recovery | Retry actions for jobs, profile/assets, skills/evidence, detail/readiness/analysis and interview queries. Detail asset controls wait for successful loading; failures do not masquerade as empty choices. |
| 29 | Disclosure accessibility | Expanded state and controlled-region IDs on saved plans, known skills, advanced details, interview insights and research sources. Native details used for funnel/coverage. Shared field errors have separate descriptions without changing control names. |
| 30 | Unambiguous dates | Shared timestamps include the year; inspected in browser job history, tracker and assets. |

Final checks: 56 backend tests, both frontend regression scripts, TypeScript checking, production build, whitespace check, desktop/laptop/mobile browser checks and browser console inspection. Browser checks used synthetic databases only; the user’s normal database was not modified. Existing `.gitignore` changes are excluded from commits.

For pending-state verification, start the fixture with `UI_FIXTURE_DELAY=3`; only synthetic POST/PATCH requests are delayed after fixture setup. AI responses are deterministic. This verifies UI loading and recovery behavior, not external AI content quality.

## Phase 1 Job detail and Application Assets — October 26, 2026

Job detail retains Overview, Resume, Cover letter and History. The document views separate preparation, generation history, editing/review and exports into responsive sections, reusing the existing workflow components. History links reveal and focus the owning document history after its data loads. Application Assets hosts the extracted reusable editors and the single source manager, with explicit links between reusable information and approved tailoring inputs.

The existing draft keys, generation requests, saved revisions, content approvals, preview receipts and export APIs are unchanged. No backend or data migrations are included. Dashboard content, Jobs intake and deferred tools remain outside this checkpoint.

Validation completed:

- 54 desktop/mobile browser checks passed across `asset-workspace`, `navigation`, `shared-foundation`, `resume-generation`, `resume-review`, `resume-exports`, `cover-letters` and `tailoring-sources`.
- After final presentation adjustments, 10 affected workflow checks passed again and captured all eight Job/Assets views at desktop and mobile sizes.
- Tests switch views with unsaved resume bullets, letter sentences, application-history notes, reusable asset drafts and selected upload files. Readiness links focus the visible editor even when another retained editor has the same field label.
- Generation started in a document view remains recoverable after switching to another view and refreshing; navigation does not submit another generation request.
- PDF preview receipts and layout acknowledgments survive a trip through History. Selected historical revisions/renders remain selected. Downloaded historical PDF bytes match the stored SHA-256; historical letter bytes match the exact revision/variant endpoint.
- Source import remains pending through tab changes; activation still requires explicit review. Version selection, file selections, revocation and activation history remain available.
- Typecheck, production build and whitespace checks passed. The build reports existing lint warnings.

Run the browser suites from `frontend/` with `node node_modules/@playwright/test/cli.js test` followed by the relevant spec paths. The tests use the synthetic fixture and deterministic model responses. `review-capture.ts` records actual pages from the top and hides only the Next.js development indicator. Captures are written under `frontend/test-results/`; the local review gallery for this checkpoint is `frontend/logs/phase1-review/index.html` (generated, ignored by Git).

## Phase 1 acceptance — October 26, 2026

The complete browser suite passed: 80 desktop/mobile checks covering navigation, legacy links, browser history, intake, reusable assets, source versions, document drafts, generation recovery, review and approval, exact historical exports, PDF previews/downloads, interview workflows, and synthetic backup restore. After adding keyboard coverage for local tabs, hidden views, More, and visible focus, the affected suite passed again: 8 checks. `npm run typecheck`, `npm run build`, and `git diff --check` passed.

The browser checks use a synthetic database and deterministic model responses. Live external AI behavior and real user records were not exercised. The production build still reports existing lint warnings; none block Phase 1. The desktop/mobile review gallery linked above contains 16 actual browser captures of the eight Job detail and Application Assets views. Content consolidation and feature removal remain deferred to later phases.
