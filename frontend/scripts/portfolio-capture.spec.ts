import { test, expect, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const directory = path.resolve(process.cwd(), "../docs/assets/screenshots");
const shots: { file: string; title: string; alt: string; recommended: string; viewport: { width: number; height: number } | null }[] = [];

async function capture(page: Page, file: string, title: string, alt: string, recommended: string, fullPage = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(directory, `${file}.png`), fullPage, animations: "disabled", caret: "hide", style: "nextjs-portal { display: none !important; }" });
  shots.push({ file, title, alt, recommended, viewport: page.viewportSize() });
}

test("capture the real UI with isolated fictional portfolio data", async ({ page, request, browser }) => {
  await mkdir(directory, { recursive: true });
  const manifest = await (await request.get("http://127.0.0.1:8120/api/demo/manifest")).json();
  expect(manifest.fictional).toBe(true);
  expect(manifest.candidate).toBe("Alex Rivera");

  await page.setViewportSize({ width: 1920, height: 1100 });
  await page.goto("/jobs?sort=company");
  await expect(page.getByRole("heading", { name: "Job Tracker", exact: true })).toBeVisible();
  await expect(page.getByRole("table").getByText("Cedarline Studio", { exact: true })).toBeVisible();
  await capture(page, "01-jobs-tracker", "Jobs tracker", "JobPilot Jobs tracker with fictional employers, application stages, salaries, and filters.", "Primary website image: the day-to-day job search workspace.");
  await page.setViewportSize({ width: 1600, height: 1100 });

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Application Sankey", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View funnel jobs", exact: true })).toHaveText("30 tracked jobs");
  await capture(page, "02-dashboard", "Dashboard", "JobPilot Dashboard showing a proportional application Sankey and summary metrics for fictional applications.", "Primary website image: application progress at a glance.");

  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByLabel("Pasted page content", { exact: true }).fill(manifest.posting);
  await page.getByRole("button", { name: "Extract fields", exact: true }).click();
  await expect(page.getByLabel("Company", { exact: true })).toHaveValue("Cedarline Studio");
  await expect(page.getByRole("button", { name: "Tailor resume", exact: true })).toBeEnabled();
  await capture(page, "03-job-intake", "Job intake", "JobPilot extracts a fictional posting into editable job fields with Save, Apply, Tailor resume, and Archive actions.", "Supporting image: turn a job posting into a reviewed opportunity.");

  await page.goto("/dashboard?tab=outcomes&group=category");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("heading", { name: "32 saved jobs in this cohort", exact: true })).toBeVisible();
  await capture(page, "04-outcomes", "Outcomes comparisons", "Compact JobPilot table comparing saved applications, interviews, offers, and conversion rates across fictional role categories.", "Supporting image: compare outcomes without a long page of cards.");

  await page.goto(`/jobs/${manifest.hero_job_id}`);
  await expect(page.getByRole("heading", { name: /Cedarline Studio/ })).toBeVisible();
  await expect(page.getByText("Saved job fields", { exact: true })).toBeVisible();
  await capture(page, "05-job-overview", "Job overview", "A fictional Cedarline Studio role in JobPilot, with saved job facts, application context, and analysis controls.", "Supporting image: keep a job's information and workflows together.");

  await page.goto(`/jobs/${manifest.hero_job_id}?tab=resume`);
  await page.getByLabel("I reviewed this complete saved job description.").check();
  await page.getByRole("button", { name: "Generate tailored resume", exact: true }).click();
  const review = page.getByRole("region", { name: "Resume review and editing", exact: true });
  await expect(review.getByLabel("Resume draft preview")).toContainText("Alex Rivera");
  await review.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await page.getByRole("button", { name: "Open larger text preview", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Saved resume text preview", exact: true })).toBeVisible();
  await capture(page, "06-resume-tailoring", "Resume tailoring", "JobPilot reviewing an evidence-backed resume draft for the fictional candidate Alex Rivera.", "Supporting image: generated content remains reviewable and editable.");

  await page.goto("/dashboard?tab=skills");
  await expect(page.getByRole("heading", { name: "Saved projects & plans", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "API reliability lab", exact: true }).click();
  await capture(page, "07-skills-learning", "Learning through projects", "JobPilot shows fictional saved project ideas and progress for API reliability and retrieval evaluation.", "Supporting image: turn recurring skill gaps into saved project work.");

  await page.goto(`/interview?resumeSessionId=${manifest.practice_session_id}`);
  await page.getByLabel("Your answer", { exact: true }).fill(manifest.answer);
  await page.getByRole("button", { name: "Evaluate answer", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Feedback", exact: true })).toBeVisible();
  await capture(page, "08-interview-practice", "Interview practice", "JobPilot Interview Practice with a fictional answer, timing controls, and illustrative coaching feedback.", "Supporting image: practice an answer and review targeted feedback.");

  const mobile = await browser.newContext({ baseURL: "http://127.0.0.1:3120", viewport: { width: 430, height: 932 }, deviceScaleFactor: 2, timezoneId: "America/New_York", colorScheme: "light" });
  const phone = await mobile.newPage();
  await phone.goto("/jobs?status=Applied");
  await expect(phone.getByRole("heading", { name: "Job Tracker", exact: true })).toBeVisible();
  await expect(phone.getByText("Harborlight Systems", { exact: true })).toHaveCount(0);
  await capture(phone, "09-jobs-mobile", "Jobs on mobile", "JobPilot's mobile job tracker with fictional application cards and status filters.", "Mobile companion to the Jobs hero; an actual viewport capture.");
  await phone.goto("/dashboard");
  await expect(phone.getByRole("heading", { name: "Application Sankey", exact: true })).toBeVisible();
  await capture(phone, "10-dashboard-mobile", "Dashboard on mobile", "JobPilot mobile Dashboard with summary metrics and a horizontally scrollable application Sankey using demo records.", "Mobile companion to the Dashboard hero; full page for flexible cropping.", true);
  await mobile.close();

  for (const target of [page]) expect(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await writeFile(path.join(directory, "manifest.json"), JSON.stringify({ captured: "2026-10-26", fictional: true, ai: "Deterministic authored demo output; no live AI evaluation.", deviceScaleFactor: 2, screenshots: shots }, null, 2));
});
