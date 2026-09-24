# UI/UX audit verification

Scope: the 32 findings from the September 24, 2026 review, plus regressions found while exercising the fixes. Verification uses the production Next.js build and a synthetic database. No production records were changed.

## Automated checks

- `cd backend; py -3.13 -m pytest -q -p no:cacheprovider`: 52 passing tests, including migration tests.
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
