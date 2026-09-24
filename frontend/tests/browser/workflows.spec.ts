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
  await branch.click();
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
  await page.getByRole("button", { name: "Save reviewed job", exact: true }).first().click();
  await page.getByRole("link", { name: "Open saved job" }).click();
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  await page.getByLabel("Next action", { exact: true }).fill(`Follow up ${company}`);
  await page.getByLabel("Due date", { exact: true }).fill(today);
  await page.getByRole("button", { name: "Save action", exact: true }).click();
  await expect(page.getByRole("button", { name: "Mark complete", exact: true })).toBeVisible();
  await page.goto("/dashboard");
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

test("profile draft survives reload and can be discarded", async ({ page }) => {
  await page.goto("/profile?tab=base");
  const name = page.getByLabel("Name", { exact: true });
  await expect(name).toBeVisible();
  await name.fill("Recovered browser draft");
  await expect(page.getByText(/Unsaved changes. Your draft is kept/)).toBeVisible();
  await page.reload();
  await expect(name).toHaveValue("Recovered browser draft");
  await page.getByRole("button", { name: "Discard draft", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Discard changes", exact: true }).click();
  await expect(name).toHaveValue("Synthetic UX Tester");
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
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 1})`, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Revise this answer" }).last().click();
  await page.getByLabel("Your answer", { exact: true }).fill(revisedAnswer);
  await page.getByRole("button", { name: "Evaluate answer", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 2})`, exact: true })).toBeVisible();
  await page.getByLabel("Compare with", { exact: true }).selectOption({ index: baseline });
  await expect(page.getByText(firstAnswer, { exact: true })).toBeVisible();
  await expect(page.getByRole("paragraph").filter({ hasText: revisedAnswer })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: `Answer attempts (${baseline + 2})`, exact: true })).toBeVisible();
});

test("outcome report exposes counts and contributing jobs", async ({ page }) => {
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: /saved jobs in this cohort/ })).toBeVisible();
  await page.getByLabel("Group by", { exact: true }).selectOption("category");
  await expect(page.getByText("Interview rate", { exact: true }).first()).toBeVisible();
  await page.locator("summary").first().click();
  await expect(page.getByRole("link", { name: "Open contributing job 1", exact: true }).first()).toBeVisible();
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
