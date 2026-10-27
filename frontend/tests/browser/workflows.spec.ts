import { captureWorkspace, openAnalytics } from "./review-capture";
import { test, expect } from "@playwright/test";

const backend = "http://127.0.0.1:8100";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status === "passed") {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath("verified.png"), fullPage: true });
  }
});

test("funnel terminal branch opens the exact cohort", async ({ page }) => {
  await page.goto("/dashboard");
  const branch = page.getByRole("link", { name: "1 jobs rejected after Tech Screen", exact: true });
  await expect(branch).toHaveCount(1);
  // Target the painted label; a curved SVG link's bounding-box center can be empty.
  await branch.locator("tspan").first().click();
  await expect(page).toHaveURL(/funnel=Rejected.*from=Tech%20Screen/);
  await expect(page.getByText("Synthetic Rejected Co", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Synthetic Applied Co", { exact: true })).toHaveCount(0);
});

test("create a job, schedule an action, reschedule, complete and reopen", async ({ page }, testInfo) => {
  const company = `Browser ${testInfo.project.name} ${Date.now()}`;
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByRole("button", { name: "Manual entry", exact: true }).click();
  await page.getByLabel("Company", { exact: true }).fill(company);
  await page.getByLabel("Role title", { exact: true }).fill("Browser Engineer");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("link", { name: "Open saved job" }).click();
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  await page.getByLabel("Next action", { exact: true }).fill(`Follow up ${company}`);
  await page.getByLabel("Due date", { exact: true }).fill(today);
  await page.getByRole("button", { name: "Save action", exact: true }).click();
  await expect(page.getByRole("button", { name: "Mark complete", exact: true })).toBeVisible();
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /^Today/ }).click();
  const row = page.getByRole("listitem").filter({ hasText: `Follow up ${company}` });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Edit / reschedule" }).click();
  await row.getByLabel("Due date", { exact: true }).fill("2000-01-01");
  await row.getByRole("button", { name: "Save action", exact: true }).click();
  await expect(row).toHaveCount(0);
  await page.getByRole("button", { name: /^Overdue/ }).click();
  await row.getByRole("button", { name: "Complete", exact: true }).click();
  await page.getByRole("button", { name: /^Completed/ }).click();
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Reopen", exact: true }).click();
  await page.getByRole("button", { name: /^Overdue/ }).click();
  await expect(row).toBeVisible();
});

test("profile draft survives reload and can be discarded", async ({ page, request }) => {
  const savedName = (await (await request.get(`${backend}/api/profile`)).json()).name;
  await page.goto("/profile?tab=base");
  const name = page.getByLabel("Name", { exact: true });
  await expect(name).toBeVisible();
  await name.fill("Recovered browser draft");
  await expect(page.getByText(/Unsaved changes. Your draft is kept/)).toBeVisible();
  await page.reload();
  await expect(name).toHaveValue("Recovered browser draft");
  await page.getByRole("button", { name: "Discard draft", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Discard changes", exact: true }).click();
  await expect(name).toHaveValue(savedName);
  expect((await (await request.get(`${backend}/api/profile`)).json()).name).toBe(savedName);
});

test("timed answers preserve revisions and compare attempts", async ({ page, request }) => {
  const response = await request.post(`${backend}/api/interview/practice-sets`, { data: { target_role: `Browser practice ${Date.now()}`, count: 1 } });
  expect(response.ok()).toBeTruthy();
  const practice = await response.json();
  const baseline = (await (await request.get(`${backend}/api/interview/questions/${practice.questions[0].id}/attempts`)).json()).length;
  const firstAnswer = `First API answer ${practice.session_id}`;
  const revisedAnswer = `Revised answer with results ${practice.session_id}`;
  await page.goto(`/interview?resumeSessionId=${practice.session_id}`);
  await page.getByLabel("Your answer", { exact: true }).fill(firstAnswer);
  await page.getByRole("button", { name: "Start timer", exact: true }).click();
  await expect(page.getByRole("timer")).not.toHaveText("0:00");
  await page.reload();
  await expect(page.getByRole("button", { name: "Pause timer" })).toBeVisible();
  await page.getByRole("button", { name: "Evaluate answer", exact: true }).click();
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 1})`, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Revise this answer" }).last().click();
  await page.getByLabel("Your answer", { exact: true }).fill(revisedAnswer);
  await page.getByRole("button", { name: "Evaluate answer", exact: true }).click();
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 2})`, exact: true })).toBeVisible();
  await page.getByLabel("Compare with", { exact: true }).selectOption({ index: baseline });
  await expect(page.getByText(firstAnswer, { exact: true })).toBeVisible();
  await expect(page.getByRole("paragraph").filter({ hasText: revisedAnswer })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 2})`, exact: true })).toBeVisible();
});

test("outcome report exposes compact counts and expandable job titles", async ({ page, request }, info) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: /saved jobs in this cohort/ })).toBeVisible();
  await page.getByLabel("Group by", { exact: true }).selectOption("category");
  const report = await (await request.get(`${backend}/api/reports/outcomes`)).json();
  const row = report.groups.category[0];
  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader")).toHaveText(["Role category", "Saved", "Applied", "Interviews", "Interview rate", "Offers", "Offer rate", "Jobs"]);
  await expect(page.getByRole("heading", { name: /contributing jobs$/ })).toHaveCount(0);
  const view = page.getByRole("button", { name: `View ${row.saved} contributing jobs for ${row.label}`, exact: true });
  const summary = table.getByRole("row").filter({ has: view });
  await expect(summary.getByRole("cell")).toHaveText([String(row.saved), String(row.applied), String(row.interviews), row.interview_rate === null ? "—" : `${row.interview_rate}%`, String(row.offers), row.offer_rate === null ? "—" : `${row.offer_rate}%`, "View"]);
  await page.route(`${backend}/api/jobs?*`, route => route.fulfill({ status: 503, json: { detail: "Synthetic job titles unavailable" } }));
  await view.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: `Hide ${row.saved} contributing jobs for ${row.label}`, exact: true })).toHaveAttribute("aria-expanded", "true");
  const details = table.getByRole("row").filter({ has: page.getByRole("heading", { name: `${row.saved} contributing jobs`, exact: true }) });
  await expect(details.getByRole("alert")).toContainText("Job titles could not load");
  await expect(details.getByRole("link", { name: "Open contributing job 1", exact: true })).toHaveAttribute("href", `/jobs/${row.job_ids[0]}`);
  await page.unroute(`${backend}/api/jobs?*`);
  await details.getByRole("button", { name: "Retry job titles", exact: true }).click();
  const job = await (await request.get(`${backend}/api/jobs/${row.job_ids[0]}`)).json();
  await expect(details.getByRole("link", { name: job.role_title, exact: true }).first()).toBeVisible();
  await expect(details.getByRole("link")).toHaveCount(row.job_ids.length);
  expect(await details.getByRole("link").evaluateAll(links => links.map(link => link.getAttribute("href")))).toEqual(row.job_ids.map((id: string) => `/jobs/${id}`));
  await captureWorkspace(page, info, "outcomes-expanded.png");
  await page.getByRole("button", { name: `Hide ${row.saved} contributing jobs for ${row.label}`, exact: true }).click();
  await expect(details).toBeHidden();
  if (info.project.name === "mobile") {
    const scroller = page.getByRole("region", { name: "Outcome comparisons", exact: true });
    await scroller.evaluate(element => { element.scrollLeft = element.scrollWidth; });
    await expect(table.getByRole("columnheader", { name: "Offer rate", exact: true })).toBeInViewport();
    await scroller.evaluate(element => { element.scrollLeft = 0; });
  }
  await page.getByRole("button", { name: `View ${row.saved} contributing jobs for ${row.label}`, exact: true }).evaluate(async element => { await Promise.all(element.getAnimations({ subtree: true }).map(animation => animation.finished)); });
  await captureWorkspace(page, info, "outcomes-table.png");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
  await openAnalytics(page);
  await page.getByLabel("Jobs saved on or after (UTC)", { exact: true }).fill("2099-01-01");
  await expect(page.getByText("No jobs in this date range.")).toBeVisible();
});

test("download, preview and restore a synthetic backup", async ({ page }) => {
  await page.goto("/data");
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download full backup", exact: true }).click();
  const download = await downloadEvent;
  const path = await download.path();
  expect(path).toBeTruthy();
  await page.getByLabel("Backup file", { exact: true }).setInputFiles(path!);
  await page.getByRole("button", { name: "Preview backup", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Backup contents" })).toBeVisible();
  const restore = page.getByRole("button", { name: "Replace data with this backup", exact: true });
  await expect(restore).toBeDisabled();
  await page.getByLabel("Type RESTORE to replace all saved data", { exact: true }).fill("RESTORE");
  await restore.click();
  await expect(page.getByText("Restore complete. Your restored data is ready.")).toBeVisible();
  const recoveryEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download pre-restore recovery backup" }).click();
  expect((await recoveryEvent).suggestedFilename()).toBe("job-pilot-before-restore.json");
});
