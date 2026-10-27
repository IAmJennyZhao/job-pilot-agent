# JobPilot page architecture

Current as of October 26, 2026. This document describes the implemented product structure, page ownership and compatibility contracts.

## Navigation

```text
Dashboard
  Overview
  Outcomes
  Skills & learning
Jobs
  Tracker page — no single-item tab bar
  Job detail: Overview / Resume / Cover letter / History
Application Assets
  Resumes / Base profile / Cover letters / Tailoring sources
  More: Coverage audit
Interview
  Practice / History
  Session detail and contextual More controls

Bottom utility: Export & backups
```

There are four sidebar destinations. Dashboard has no More menu. Existing contextual shortcuts remain on other pages. Desktop uses the sage sidebar; mobile uses the same destinations in a labelled navigation drawer. Local tabs wrap and preserve their full labels.

## Page ownership

| Page | Current responsibility | Main implementation |
| --- | --- | --- |
| Dashboard Overview | Active/stale/missing-data metrics, proportional Application Sankey, then collapsed Analytics cohort and Your next actions. Coverage/recurring risks is removed. | `frontend/src/app/dashboard/page.tsx` |
| Outcomes | Compact source/category/resume comparison table; View expands contributing job titles, companies and current statuses. Definitions are collapsed. | `components/dashboard/outcomes-view.tsx` |
| Skills & learning | Project-first generation, saved project/plan progress, moved Top Skill Gaps, detailed gap evidence and known skills. | `components/dashboard/skills-view.tsx`, `top-skill-gaps.tsx` |
| Jobs tracker | Intake, extraction/manual entry, review/corrections, duplicate checks, filters, sorting, inline edits and previews. | `frontend/src/app/jobs/page.tsx` |
| Job Overview | Canonical saved facts, dated analysis snapshot, status/actions, links, company/prep context and reusable asset selection/ranking. | `frontend/src/app/jobs/[jobId]/page.tsx` |
| Job Resume | Preparation → generation → review/edit → rendering/preview → exact-version exports. | `components/tailoring/resume-workspace.tsx`, `resume-review.tsx`, `resume-exports.tsx` |
| Job Cover letter | Independent generation, variant/sentence editing, evidence review, revisions and TXT/Markdown exports. | `components/tailoring/letter-workspace.tsx`, `letter-review.tsx` |
| Job History | Application status events and their existing editing controls. Document histories stay with their workspaces. | Job detail page |
| Application Assets | Reusable libraries/profile, manual Ready state, merges, original files, explicit ranking/coverage and immutable source management. | `frontend/src/app/profile/page.tsx`, `components/assets/asset-views.tsx`, `tailoring/source-manager.tsx` |
| Interview Practice | Active question, answer draft, timer and current feedback. | `frontend/src/app/interview/page.tsx` |
| Interview History | Previous sessions, attempts/comparisons, recurring weaknesses, recent feedback and secondary trends. | Interview page and `interview/sessions/[sessionId]/page.tsx` |
| Export & backups | CSV, full archive, validated restore and recovery copies. | `frontend/src/app/data/page.tsx` |

Paths beginning with `frontend/` are repository-relative; other component paths are relative to `frontend/src/`.

## Intake and job provenance

Save, Apply, Tailor resume and Archive sit directly above the visible Summary field. Save and Tailor resume persist Saved; Apply records Applied; Archive records Archived. Tailor resume opens preparation without generating. Not pursuing discards the draft.

All four saved decisions use the evaluated, duplicate-protected intake transaction, persistent request key and preference hash. Manual/URL/text extraction, advanced corrections, source review and recovery remain. Backups support all four decision values without a storage migration.

Saved Job fields own the role snapshot. AI interpretation is a separate dated snapshot. Timestamps provide conservative freshness warnings, not proof of current factual accuracy; the record has no immutable analysis-input fingerprint. Browsing or editing does not regenerate analysis.

## Analytics and next actions

- Overview and Outcomes share the first-saved-date cohort: inclusive midnight UTC, with full progression history. URL `since` is canonical; `saved_since` and `outcomesSince` remain compatible aliases. An explicitly empty `since` means All time. Invalid/conflicting dates are exposed rather than silently changed.
- Health, coverage and top gaps use open opportunities. The funnel includes closed outcomes but excludes Archived. Outcomes includes archived and closed jobs. Counts and their drill-downs follow their own population definitions.
- Sankey ribbons and node bars use one proportional scale. Intermediate stops reconcile outgoing flow with node totals. Recorded/inferred stages, exact transition drill-downs, keyboard links and the count alternative remain.
- Top Skill Gaps now lives in Skills & learning and retains its Dashboard cohort. The detailed learning gap table keeps its existing population. These are labelled rather than silently equated.
- Scheduled tasks span all jobs and ignore analytics dates. Their due dates use the local calendar day. Completing/reopening/rescheduling tasks does not change job status.
- Computed stale/data suggestions follow the cohort and are deduplicated with tasks by job. Missing fit/analysis is not an action. Stale suggestions offer an explicit Mark as ghosted status update; existing task records remain intact.
- Outcomes labels are frozen when progress beyond Saved is first recorded. Resume fingerprints describe selected content, not proof of submission. Current contributing-job titles/statuses do not replace those frozen comparison labels.

## Assets, sources and documents

Reusable assets belong to Application Assets; generated job-specific documents belong to the job. Manual resume Ready, reusable completeness, AI-analysis setup, generation prerequisites, saved-content review and PDF export approval are distinct concepts. Cover letter templates are optional for generation.

Editing extracted resume fields does not modify the uploaded PDF. Download original PDF returns its saved bytes. Save, Ready and merge preserve their existing contracts; profile edits and merges never silently activate or update tailoring sources.

The existing registry owns immutable source versions, pending imports, explicit activation/revocation, concurrency checks and history. The compact active-source summary is shared with preparation. Technical details remain collapsible; importing layout references does not execute their TeX.

Document views retain their existing components and IDs. Selected revisions, unsaved local edits, historical versions and saved previews are distinguished. Resume content review and exact-render/layout approval remain separate. Exact PDF/TeX/text exports, receipts, baseline/revision/render identities and historical bytes remain bound to their saved versions. Cover letters retain independent variant/sentence review and TXT/Markdown exports; there is no letter PDF workflow.

Coverage Audit remains an explicit heuristic: the existing 30-day activity window and threshold below 45 are unchanged. Keyword and explicit AI ranking remain accessible without automatically selecting assets.

## State, Interview and compatibility

Visited local views stay mounted to preserve edits and in-flight work. Browser/session recovery and cross-tab rules retain their existing owners; server persistence recovers generation. Recovery warnings and unsaved edits cannot be silently discarded. Navigation does not trigger generation, activation, approval or application submission.

Saved project/plan IDs, completion IDs and progress remain stable. Practice retains active answers and timers through History navigation and refresh. Timers do not submit automatically. History owns previous attempts and detailed insights. Knowledge and Interview skills trends are overlapping subsets of overall scores, not independent subscores. Continue unanswered questions uses the existing continuation rule; it is not a global historical-answer revision action.

| URL | Compatibility |
| --- | --- |
| `/dashboard?tab=…` | Overview, Outcomes and Skills selections survive direct entry, refresh and browser history, with applicable filters. |
| `/reports`, `/skills` | Redirect to their Dashboard views, retaining applicable query filters. |
| `/jobs`, `/jobs?tab=tracker` | Tracker and legacy single-view links remain functional. |
| `/jobs/:id?tab=…` | Overview, Resume, Letter and History use the existing URL-aware selectors. |
| `/jobs/:id?tailoring=prepare#tailoring-preparation` | Opens Resume preparation; existing history/section anchors retain their owner views. |
| `/profile` and existing tab/coverage links | Continue to open Application Assets and the correct local view. |
| `/interview` and session/legacy links | Preserve active work and select the correct Practice/History owner. |
| `/data` | Export & backups utility. |

The route implementation remains authoritative for accepted aliases. See [verification](verification.md) and the [document-workflow references](README.md#document-workflows) for checks and detailed contracts.
