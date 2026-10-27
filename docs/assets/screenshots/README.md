# JobPilot website screenshots

Captured October 26, 2026 from the real completed interface. **Use Jobs tracker and Dashboard as the two primary project-page images.** The other images support individual features.

All people, companies, application histories, evidence and AI responses are fictional demo content. The set uses 32 applications (30 non-archived), candidate Alex Rivera and reserved `.example.test` domains. It is independent of the owner's database. Suggested website disclosure: **“Screens shown with fictional demo data.”** AI feedback is authored and deterministic, not a live quality benchmark.

[Open the gallery](index.html). WebP files are optimized website copies, capped at 1920px wide. PNGs are original 2× browser captures. No fields, warnings or results were painted over; only Next's development indicator is hidden. Desktop captures are viewport crops of scrollable pages. The mobile Dashboard is a full-page capture; the mobile Jobs image is a viewport capture. Application Assets was not redesigned or featured.

| Order | Website copy | Full-resolution original | Web size |
| --- | --- | --- | --- |
| 1 | [Jobs tracker](01-jobs-tracker.webp) | [PNG](01-jobs-tracker.png), 3840×2200 | 167 KB |
| 2 | [Dashboard](02-dashboard.webp) | [PNG](02-dashboard.png), 3200×2200 | 84 KB |
| 3 | [Job intake](03-job-intake.webp) | [PNG](03-job-intake.png), 3200×2200 | 80 KB |
| 4 | [Outcomes comparisons](04-outcomes.webp) | [PNG](04-outcomes.png), 3200×2200 | 59 KB |
| 5 | [Job overview](05-job-overview.webp) | [PNG](05-job-overview.png), 3200×2200 | 123 KB |
| 6 | [Resume tailoring](06-resume-tailoring.webp) | [PNG](06-resume-tailoring.png), 3200×2200 | 154 KB |
| 7 | [Learning through projects](07-skills-learning.webp) | [PNG](07-skills-learning.png), 3200×2200 | 84 KB |
| 8 | [Interview practice](08-interview-practice.webp) | [PNG](08-interview-practice.png), 3200×2200 | 109 KB |
| 9 | [Jobs on mobile](09-jobs-mobile.webp) | [PNG](09-jobs-mobile.png), 860×1864 | 63 KB |
| 10 | [Dashboard on mobile](10-dashboard-mobile.webp) | [PNG](10-dashboard-mobile.png), 860×5106 | 171 KB |

## Captions and alt text

### Jobs tracker

Primary website image: the day-to-day job search workspace.

Alt text: JobPilot Jobs tracker with fictional employers, application stages, salaries, and filters.

### Dashboard

Primary website image: application progress at a glance.

Alt text: JobPilot Dashboard showing a proportional application Sankey and summary metrics for fictional applications.

### Job intake

Supporting image: turn a job posting into a reviewed opportunity.

Alt text: JobPilot extracts a fictional posting into editable job fields with Save, Apply, Tailor resume, and Archive actions.

### Outcomes comparisons

Supporting image: compare outcomes without a long page of cards.

Alt text: Compact JobPilot table comparing saved applications, interviews, offers, and conversion rates across fictional role categories.

### Job overview

Supporting image: keep a job's information and workflows together.

Alt text: A fictional Cedarline Studio role in JobPilot, with saved job facts, application context, and analysis controls.

### Resume tailoring

Supporting image: generated content remains reviewable and editable.

Alt text: JobPilot reviewing an evidence-backed resume draft for the fictional candidate Alex Rivera.

### Learning through projects

Supporting image: turn recurring skill gaps into saved project work.

Alt text: JobPilot shows fictional saved project ideas and progress for API reliability and retrieval evaluation.

### Interview practice

Supporting image: practice an answer and review targeted feedback.

Alt text: JobPilot Interview Practice with a fictional answer, timing controls, and illustrative coaching feedback.

### Jobs on mobile

Mobile companion to the Jobs hero; an actual viewport capture.

Alt text: JobPilot's mobile job tracker with fictional application cards and status filters.

### Dashboard on mobile

Mobile companion to the Dashboard hero; full page for flexible cropping.

Alt text: JobPilot mobile Dashboard with summary metrics and a horizontally scrollable application Sankey using demo records.

## Recreate and package

Install the project's backend development dependencies and frontend dependencies first. No real provider key is required.

```powershell
cd frontend
npx playwright install chromium
node node_modules/@playwright/test/cli.js test -c playwright.portfolio.config.ts
node scripts/package-portfolio.mjs
node scripts/verify-portfolio.mjs
```

The dedicated backend creates a new temporary SQLite database and authors its records through existing APIs. It never opens the normal database. AI and research are deterministic local fixtures; unexpected provider requests fail. Demo servers bind only to 127.0.0.1 on ports 3120/8120 and refuse server reuse. The frontend uses a fresh source snapshot under ignored repository logs, with separate build output and no .env copied. Existing app source and assets are not edited for the images.

The capture exercises intake, cohort reporting, ordinary resume generation/content review, saved project progress, and Interview evaluation using demo records. It is an asset-production check, not a replacement for the regression suite. Rendering/export approval is not claimed by the text-preview image.

The packager uses Sharp supplied with Next.js, verifies the ten-image manifest, writes WebP copies/gallery, and creates `frontend/logs/jobpilot-portfolio-screenshots.zip`. That convenience ZIP is ignored by Git. Original images, website copies, this guide and `manifest.json` are retained in this directory. The manifest records dimensions, file sizes and SHA-256 hashes.
