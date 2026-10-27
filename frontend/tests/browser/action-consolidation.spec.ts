import { openAnalytics } from "./review-capture";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { captureWorkspace, captureWorkspaceArea } from "./review-capture";

const backend = "http://127.0.0.1:8100";
test.use({ timezoneId: "America/New_York" });

async function jobWithTask(request: APIRequestContext, title: string, due = "2000-01-01", status = "Applied") {
  const response = await request.post(`${backend}/api/jobs`, { data: { company: title, role_title: "Test Engineer", status, source_content: "Build reliable Python APIs.", extraction_confidence: 0 } });
  expect(response.ok()).toBeTruthy();
  const job = await response.json();
  const detail = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  expect((await request.patch(`${backend}/api/jobs/${job.id}/status-events/${detail.status_events[0].id}`, { data: { changed_at: "2000-01-01T00:00:00Z" } })).ok()).toBeTruthy();
  expect((await request.put(`${backend}/api/actions/${job.id}`, { data: { title, due_date: due } })).ok()).toBeTruthy();
  return job;
}

test("one job retains all reasons, task state and an editing draft across views", async ({ page, request }, info) => {
  const title = `Consolidation ${info.project.name} ${Date.now()}`;
  const job = await jobWithTask(request, title);
  const before = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  await page.goto("/dashboard");
  const agenda = page.locator("section").filter({ has: page.locator("#search-health") }).last();
  const row = agenda.locator(`[data-job-id="${job.id}"]`);
  await expect(row).toBeVisible();
  await expect(row).toHaveCount(1);
  await expect(row.getByText(/No movement for/)).toBeVisible();
  await expect(row.getByText("Missing fit score and job analysis", { exact: true })).toHaveCount(0);
  await expect(row.getByRole("button", { name: "Mark as ghosted", exact: true })).toBeVisible();
  await expect(row.getByText("Missing pay", { exact: true })).toBeVisible();
  await expect(row.getByText("Extraction confidence 0 (below 80)", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Search Health", exact: true })).toHaveCount(0);
  await captureWorkspaceArea(page, info, "combined-actions.png", agenda);
  await captureWorkspace(page, info, "dashboard-compact.png");

  await row.getByRole("button", { name: "Edit / reschedule" }).click();
  await row.getByLabel("Next action", { exact: true }).fill(`${title} edited`);
  await row.getByLabel("Due date", { exact: true }).fill("2000-01-02");
  await expect(row.getByRole("button", { name: "Complete", exact: true })).toBeDisabled();
  await agenda.getByRole("button", { name: /^Upcoming/ }).click();
  await expect(row).toBeHidden();
  await agenda.getByRole("button", { name: /^To do/ }).click();
  const tabs = page.getByRole("navigation", { name: "Dashboard views" });
  await tabs.getByRole("button", { name: "Outcomes", exact: true }).click();
  await page.goBack();
  await expect(row.getByLabel("Next action", { exact: true })).toHaveValue(`${title} edited`);
  await expect(row.getByLabel("Due date", { exact: true })).toHaveValue("2000-01-02");
  await openAnalytics(page);
  await page.getByLabel("Jobs saved on or after (UTC)", { exact: true }).fill("2099-01-01");
  await expect(row.getByText("Computed suggestions · not scheduled", { exact: true })).toHaveCount(0);
  await expect(row.getByLabel("Next action", { exact: true })).toHaveValue(`${title} edited`);
  await openAnalytics(page);
  await page.getByRole("button", { name: "All time", exact: true }).click();
  await row.getByRole("button", { name: "Save action", exact: true }).click();
  await expect(row.getByText(`${title} edited`, { exact: true })).toBeVisible();
  await page.route(`${backend}/api/actions/${job.id}`, route => route.request().method() === "PUT"
    ? route.fulfill({ status: 503, json: { detail: "Synthetic save failure" } }) : route.continue());
  await row.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(row.getByRole("alert")).toContainText("Synthetic save failure");
  expect((await (await request.get(`${backend}/api/actions/${job.id}`)).json()).completed_at).toBeNull();
  await page.unroute(`${backend}/api/actions/${job.id}`);
  await row.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(row.getByText("Scheduled task · Completed", { exact: true })).toBeVisible();
  await expect(row.getByText(/No movement for/)).toBeVisible();
  await expect(row.getByText("Missing pay", { exact: true })).toBeVisible();
  const after = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  for (const field of ["status", "status_events", "updated_at"]) expect(after[field]).toEqual(before[field]);
  await captureWorkspaceArea(page, info, "completed-with-suggestions.png", row);

  await openAnalytics(page);
  await page.getByLabel("Jobs saved on or after (UTC)", { exact: true }).fill("2099-01-01");
  await expect(row).toBeHidden();
  await agenda.getByRole("button", { name: /^Completed/ }).click();
  await expect(row).toBeVisible();
  await expect(row.getByText("Computed suggestions · not scheduled", { exact: true })).toHaveCount(0);
  await row.getByRole("button", { name: "Reopen", exact: true }).click();
  await agenda.getByRole("button", { name: /^Overdue/ }).click();
  await expect(row).toBeVisible();
  await page.reload();
  await expect(row).toBeVisible();
  await expect(row.getByText("Due 2000-01-02 · local calendar date", { exact: true })).toBeVisible();
  expect((await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).status).toBe("Applied");
});

test("local midnight moves due tasks without analytics filtering or status changes", async ({ page, request }) => {
  await page.clock.install({ time: new Date("2035-01-16T04:59:50Z") }); // Jan 15, 23:59:50 New York.
  const today = await jobWithTask(request, `Midnight today ${Date.now()}`, "2035-01-15", "Archived");
  const tomorrow = await jobWithTask(request, `Midnight tomorrow ${Date.now()}`, "2035-01-16", "Rejected");
  await page.goto("/dashboard?since=2099-01-01");
  const agenda = page.locator("section").filter({ has: page.locator("#search-health") }).last();
  await agenda.getByRole("button", { name: /^Today/ }).click();
  await expect(agenda.locator(`[data-job-id="${today.id}"]`)).toBeVisible();
  await expect(agenda.locator(`[data-job-id="${tomorrow.id}"]`)).toBeHidden();
  await page.clock.fastForward(45000);
  await expect(agenda.locator(`[data-job-id="${tomorrow.id}"]`)).toBeVisible();
  await expect(agenda.locator(`[data-job-id="${today.id}"]`)).toBeHidden();
  await agenda.getByRole("button", { name: /^Overdue/ }).click();
  await expect(agenda.locator(`[data-job-id="${today.id}"]`)).toBeVisible();
  await expect(agenda.getByText("Computed suggestions · not scheduled", { exact: true })).toHaveCount(0);
});

test("all suggestions stay accessible and task request failures do not hide them", async ({ page, request }) => {
  for (let i = 0; i < 10; i++) expect((await request.post(`${backend}/api/jobs`, { data: { company: `Uncapped ${Date.now()} ${i}`, role_title: "Engineer" } })).ok()).toBeTruthy();
  const summary = await (await request.get(`${backend}/api/dashboard/summary`)).json();
  await page.route(`${backend}/api/actions`, route => route.fulfill({ status: 503, json: { detail: "Synthetic tasks unavailable" } }));
  await page.goto("/dashboard");
  const agenda = page.locator("section").filter({ has: page.locator("#search-health") }).last();
  await expect(agenda.getByRole("button", { name: "Retry scheduled tasks" })).toBeVisible();
  await agenda.getByRole("button", { name: /^Suggestions/ }).click();
  await expect(agenda.getByRole("listitem")).toHaveCount(8);
  await agenda.getByRole("button", { name: /^Show all/ }).click();
  const actionable = summary.action_suggestions.filter((suggestion: { reasons: { kind: string }[] }) => suggestion.reasons.some(reason => reason.kind !== "analysis"));
  await expect(agenda.getByRole("listitem")).toHaveCount(actionable.length);
  expect(new Set(await agenda.getByRole("listitem").evaluateAll(rows => rows.map(row => row.getAttribute("data-job-id")))).size).toBe(actionable.length);
  await page.unroute(`${backend}/api/actions`);
  await agenda.getByRole("button", { name: "Retry scheduled tasks" }).click();
  await expect(agenda.getByRole("button", { name: "Retry scheduled tasks" })).toHaveCount(0);
  const pending = await jobWithTask(request, `Survives summary failure ${Date.now()}`);
  await page.route(`${backend}/api/dashboard/summary*`, route => route.fulfill({ status: 503, json: { detail: "Synthetic suggestions unavailable" } }));
  await page.reload();
  await expect(agenda.getByRole("button", { name: "Retry suggestions" })).toBeVisible();
  await expect(agenda.locator(`[data-job-id="${pending.id}"]`)).toBeVisible();
});

test("missing analysis is not a task and marking stale jobs ghosted is explicit and recoverable", async ({ page, request }) => {
  const fresh = await (await request.post(`${backend}/api/jobs`, { data: { company: `Analysis only ${Date.now()}`, role_title: "Engineer", status: "Applied", pay_raw: "$150k", extraction_confidence: 90 } })).json();
  const job = await jobWithTask(request, `Explicit ghosting ${Date.now()}`);
  await page.goto("/dashboard");
  await expect(page.locator(`[data-job-id="${fresh.id}"]`)).toHaveCount(0);
  const row = page.locator(`[data-job-id="${job.id}"]`);
  await expect(row.getByRole("button", { name: "Run analysis", exact: true })).toHaveCount(0);
  await expect(row.getByText("Missing fit score and job analysis", { exact: true })).toHaveCount(0);
  const ghost = row.getByRole("button", { name: "Mark as ghosted", exact: true });
  await page.route(`${backend}/api/jobs/${job.id}`, route => route.request().method() === "PATCH" ? route.fulfill({ status: 503, json: { detail: "Synthetic ghosting failure" } }) : route.continue());
  await ghost.click();
  await expect(row.getByRole("alert")).toContainText("Synthetic ghosting failure");
  expect((await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).status).toBe("Applied");
  await page.unroute(`${backend}/api/jobs/${job.id}`);
  await ghost.click();
  await expect(row.getByText("Ghosted", { exact: true })).toBeVisible();
  await expect(ghost).toHaveCount(0);
  await expect(row.getByText(/No movement for/)).toHaveCount(0);
  const action = await (await request.get(`${backend}/api/actions/${job.id}`)).json();
  expect(action.completed_at).toBeNull();
  const detail = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  expect(detail.status).toBe("Ghosted");
  expect(detail.status_events.map((event: { to_status: string }) => event.to_status)).toEqual(["Applied", "Ghosted"]);
  await page.reload();
  await expect(row.getByText("Ghosted", { exact: true })).toBeVisible();
  await expect(row.getByRole("button", { name: "Complete", exact: true })).toBeVisible();
});
