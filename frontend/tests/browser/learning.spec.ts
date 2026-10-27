import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { captureWorkspace, captureWorkspaceArea } from "./review-capture";

const backend = "http://127.0.0.1:8100";
const generated = (page: Page) => page.getByRole("region", { name: "Generated learning output", exact: true });
const record = (page: Page, id: string) => page.locator(`[data-plan-id="${id}"]`);
async function saved(request: APIRequestContext, id: string) {
  const rows = await (await request.get(`${backend}/api/study-plans`)).json();
  return rows.find((row: { id: string }) => row.id === id);
}

test("project-only generation is primary and captures focus/options through save and reload", async ({ page, request }, info) => {
  await page.goto("/skills");
  await expect(page.getByRole("heading", { name: "Skills & learning", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate project ideas", exact: true })).toBeVisible();
  await expect(page.getByLabel("Output", { exact: true })).toBeHidden();
  const gaps = await (await request.get(`${backend}/api/skill-gaps`)).json();
  const focus = gaps.find((gap: { user_level: string }) => gap.user_level !== "high").skill_name;
  await page.getByRole("button", { name: "Choose skills", exact: true }).click();
  await page.getByRole("checkbox", { name: `Focus on ${focus}`, exact: true }).check();
  const options = page.locator("summary", { hasText: "Weekly planning & generation options" });
  await options.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Output", { exact: true })).toHaveValue("project_ideas");
  await page.getByLabel("Timeframe", { exact: true }).selectOption("1 month");
  await page.getByLabel("Available hours", { exact: true }).fill("3");
  await page.getByLabel("Time budget unit", { exact: true }).selectOption("week");
  await options.click();
  const generation = page.waitForRequest(url => url.url().endsWith("/api/ai/generate-study-plan") && url.method() === "POST");
  await page.getByRole("button", { name: "Generate project ideas", exact: true }).click();
  expect((await generation).postDataJSON()).toMatchObject({ mode: "project_ideas", timeframe: "1 month", focus_skills: [focus], time_budget_hours: 3, time_budget_unit: "week" });
  await expect(generated(page).getByRole("heading", { name: "Generated project ideas", exact: true })).toBeVisible();
  await expect(generated(page).locator("summary", { hasText: "Weekly plan & study tasks" })).toHaveCount(0);
  await generated(page).getByLabel("Save name", { exact: true }).fill(`Projects ${info.project.name} ${Date.now()}`);
  const title = await generated(page).getByLabel("Save name", { exact: true }).inputValue();
  await page.getByRole("navigation", { name: "Dashboard views" }).getByRole("button", { name: "Outcomes", exact: true }).click();
  await expect(page).toHaveURL(/tab=outcomes/);
  await page.goBack();
  await expect(generated(page).getByLabel("Save name", { exact: true })).toHaveValue(title);
  await options.click();
  await expect(page.getByLabel("Available hours", { exact: true })).toHaveValue("3");
  // Changing the next request must not relabel or rewrite the already generated result.
  await page.getByLabel("Output", { exact: true }).selectOption("weekly_plan");
  await expect(generated(page).getByRole("button", { name: "Save project ideas", exact: true })).toBeVisible();
  await page.route(`${backend}/api/study-plans`, route => route.request().method() === "POST" ? route.fulfill({ status: 503, json: { detail: "Synthetic save unavailable" } }) : route.continue());
  await generated(page).getByRole("button", { name: "Save project ideas", exact: true }).click();
  await expect(generated(page).getByRole("alert")).toContainText("Synthetic save unavailable");
  await expect(generated(page).getByLabel("Save name", { exact: true })).toHaveValue(title);
  await page.unroute(`${backend}/api/study-plans`);
  const response = page.waitForResponse(url => url.url().endsWith("/api/study-plans") && url.request().method() === "POST");
  await generated(page).getByRole("button", { name: "Save project ideas", exact: true }).click();
  const plan = await (await response).json();
  expect(plan.mode).toBe("project_ideas");
  expect(plan.plan.study_plan).toEqual([]);
  expect(plan.plan.project_ideas).toHaveLength(2);
  await record(page, plan.id).getByRole("button", { name: title, exact: true }).click();
  await record(page, plan.id).locator('[data-completion-id="project:1"]').getByRole("checkbox").click();
  await expect.poll(async () => (await saved(request, plan.id)).plan.completed_tasks).toEqual(["project:1"]);
  await page.reload();
  await record(page, plan.id).getByRole("button", { name: title, exact: true }).click();
  await expect(record(page, plan.id).locator('[data-completion-id="project:1"]').getByRole("checkbox")).toBeChecked();
  await expect(record(page, plan.id).locator('[data-completion-id="project:0"]').getByRole("checkbox")).not.toBeChecked();
  await expect(record(page, plan.id).getByRole("progressbar", { name: "Project progress", exact: true })).toHaveAttribute("value", "1");
  await captureWorkspace(page, info, "project-first-learning.png");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
});

test("existing mixed plans preserve project/task identities, errors, rename and retained disclosures", async ({ page, request }, info) => {
  const response = await request.post(`${backend}/api/study-plans`, { data: {
    title: `Existing mixed ${Date.now()}`, timeframe: "2 weeks", mode: "both", focus_skills: ["Python"],
    plan: { top_gaps: ["Python"], priority_order: ["Python"], project_ideas: ["Same project", "Same project"], study_plan: [
      { period: "Week 1", focus: "Practice", tasks: ["Repeat task", "Repeat task"] }, { period: "Week 2", focus: "Practice", tasks: ["Repeat task"] }
    ] }
  } });
  const plan = await response.json();
  const initial = ["project:0", "task:0:1", "task:1:0"];
  expect((await request.patch(`${backend}/api/study-plans/${plan.id}`, { data: { completed_tasks: initial } })).ok()).toBeTruthy();
  await page.goto("/dashboard?tab=skills");
  const row = record(page, plan.id);
  await expect(row.locator(":scope > p")).toHaveText("1 of 2 projects completed - 2 of 3 study tasks completed");
  await row.getByRole("button", { name: plan.title, exact: true }).click();
  const project = (index: number) => row.locator(`[data-completion-id="project:${index}"]`).getByRole("checkbox");
  await expect(project(0)).toBeChecked();
  await expect(project(1)).not.toBeChecked();
  const tasks = row.locator("summary", { hasText: "Weekly plan & study tasks" });
  await expect(row.locator('[data-completion-id="task:0:1"]').getByRole("checkbox")).toBeHidden();
  await page.route(`${backend}/api/study-plans/${plan.id}`, route => route.fulfill({ status: 503, json: { detail: "Synthetic progress failure" } }));
  await project(1).click();
  await expect(row.getByRole("alert")).toContainText("Progress was not saved");
  await expect(project(1)).not.toBeChecked();
  expect((await saved(request, plan.id)).plan.completed_tasks).toEqual(initial);
  await page.unroute(`${backend}/api/study-plans/${plan.id}`);
  await project(1).click();
  await expect.poll(async () => (await saved(request, plan.id)).plan.completed_tasks).toEqual([...initial, "project:1"]);
  await tasks.click();
  await row.locator('[data-completion-id="task:0:1"]').getByRole("checkbox").click();
  await expect.poll(async () => (await saved(request, plan.id)).plan.completed_tasks).toEqual(["project:0", "task:1:0", "project:1"]);
  await row.getByRole("button", { name: plan.title, exact: true }).click();
  await row.getByRole("button", { name: plan.title, exact: true }).click();
  await expect(row.locator('[data-completion-id="task:1:0"]').getByRole("checkbox")).toBeVisible();
  await row.getByRole("button", { name: "Rename plan", exact: true }).click();
  await row.getByLabel("Plan name", { exact: true }).fill(`Renamed ${plan.title}`);
  await page.getByRole("navigation", { name: "Dashboard views" }).getByRole("button", { name: "Overview", exact: true }).click();
  await page.goBack();
  await expect(row.getByLabel("Plan name", { exact: true })).toHaveValue(`Renamed ${plan.title}`);
  await row.getByLabel("Plan name", { exact: true }).press("Enter");
  await expect(row.getByRole("button", { name: `Renamed ${plan.title}`, exact: true })).toBeVisible();
  const updated = await saved(request, plan.id);
  expect(updated.id).toBe(plan.id);
  expect(updated.plan.project_ideas).toEqual(plan.plan.project_ideas);
  expect(updated.plan.study_plan).toEqual(plan.plan.study_plan);
  expect(updated.plan.completed_tasks).toEqual(["project:0", "task:1:0", "project:1"]);
  if (info.project.name === "mobile") {
    const titleBounds = (await row.getByRole("button", { name: `Renamed ${plan.title}`, exact: true }).boundingBox())!;
    const modeBounds = (await row.getByText("plan + projects", { exact: true }).boundingBox())!;
    expect(titleBounds.y + titleBounds.height).toBeLessThanOrEqual(modeBounds.y + 1);
  }
  await captureWorkspaceArea(page, info, "mixed-project-progress.png", row);
});

test("weekly and combined generation remain available with their existing metadata", async ({ page, request }) => {
  await page.goto("/dashboard?tab=skills#study-plan");
  await page.locator("#study-plan").click();
  for (const mode of ["both", "weekly_plan"]) {
    await page.getByLabel("Output", { exact: true }).selectOption(mode);
    await page.getByLabel("Timeframe", { exact: true }).selectOption("1 week");
    await page.getByLabel("Available hours", { exact: true }).fill("2");
    await page.getByLabel("Time budget unit", { exact: true }).selectOption("day");
    await page.getByRole("button", { name: mode === "both" ? "Generate plan + projects" : "Generate weekly plan", exact: true }).click();
    await expect(generated(page).locator("summary", { hasText: "Weekly plan & study tasks" })).toBeVisible();
    const title = `Mode ${mode} ${Date.now()}`;
    await generated(page).getByLabel("Save name", { exact: true }).fill(title);
    const response = page.waitForResponse(url => url.url().endsWith("/api/study-plans") && url.request().method() === "POST");
    await generated(page).getByRole("button", { name: "Save plan", exact: true }).click();
    const plan = await (await response).json();
    expect(plan).toMatchObject({ mode, timeframe: "1 week", time_budget_hours: 2, time_budget_unit: "day" });
    expect(plan.plan.project_ideas.length).toBe(mode === "both" ? 2 : 0);
    expect(plan.plan.study_plan).toHaveLength(1);
    expect((await saved(request, plan.id)).id).toBe(plan.id);
  }
});

test("gap evidence, known skills and confirmed plan deletion remain accessible", async ({ page, request }) => {
  await page.goto("/dashboard?tab=skills");
  await page.getByRole("button", { name: "Choose skills", exact: true }).click();
  const gaps = await (await request.get(`${backend}/api/skill-gaps`)).json();
  const gap = gaps.find((item: { user_level: string }) => item.user_level !== "high");
  await page.getByRole("button", { name: `View evidence for ${gap.skill_name}`, exact: true }).click();
  await expect(page.getByRole("dialog", { name: `Evidence for ${gap.skill_name}`, exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel(`Your level in ${gap.skill_name}`, { exact: true }).selectOption("high");
  await expect(page.getByRole("button", { name: /^Known skills/ })).toBeVisible();
  await page.getByRole("button", { name: /^Known skills/ }).click();
  await page.getByLabel(`Your level in ${gap.skill_name}`, { exact: true }).selectOption(gap.user_level);
  const response = await request.post(`${backend}/api/study-plans`, { data: { title: `Delete selected ${Date.now()}`, timeframe: "1 week", mode: "project_ideas", plan: { top_gaps: [], priority_order: [], study_plan: [], project_ideas: ["Temporary project"] } } });
  const plan = await response.json();
  await page.reload();
  const row = record(page, plan.id);
  await row.getByRole("button", { name: "Delete plan", exact: true }).click();
  await page.getByRole("dialog", { name: "Confirm change", exact: true }).getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Delete plan", exact: true }).click();
  await page.getByRole("dialog", { name: "Confirm change", exact: true }).getByRole("button", { name: "Delete", exact: true }).click();
  await expect(row).toHaveCount(0);
  expect(await saved(request, plan.id)).toBeUndefined();
  expect((await (await request.get(`${backend}/api/study-plans`)).json()).length).toBeGreaterThan(0);
});
