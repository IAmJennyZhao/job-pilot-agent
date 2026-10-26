import { captureWorkspace } from "./review-capture";
import { test, expect, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backend = "http://127.0.0.1:8100";
async function prepare(request: APIRequestContext) {
  const command = process.platform === "win32" ? "py" : "python";
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c", "import sys,json;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;print(json.dumps(import_payload()))"];
  const bundle = JSON.parse(execFileSync(command, args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.style_guide += ` review ${Date.now()}`;
  const source = await (await request.post(`${backend}/api/profile/tailoring-sources/import`, { data: bundle })).json();
  const state = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  expect((await request.post(`${backend}/api/profile/tailoring-sources/${source.id}/activate`, { data: { expected_hash: source.bundle_hash, expected_active_id: state.active_id } })).ok()).toBeTruthy();
  const job = await (await request.post(`${backend}/api/jobs`, { data: { company: `Review ${Date.now()}`, role_title: "Backend Engineer", source_content: "Build Python services.", status: "Applied" } })).json();
  const { readiness } = await (await request.get(`${backend}/api/jobs/${job.id}/tailoring`)).json();
  const run = await (await request.post(`${backend}/api/jobs/${job.id}/tailoring/resume`, { data: { request_key: crypto.randomUUID(), expected_input_hash: readiness.input_hash, reviewed_description_hash: readiness.description_hash, acknowledged_evaluation_hash: readiness.evaluation.evaluation_hash } })).json();
  expect(run.state).toBe("completed");
  return { job, run, url: `${backend}/api/tailoring/resumes/${run.revision.id}` };
}

test.afterEach(async ({ page }, info) => {
  if (info.status === "passed") {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.getByRole("region", { name: "Resume review and editing" }).screenshot({ path: info.outputPath("resume-review.png") });
  }
});

test("advisory becomes stale after edits and empty drafts cannot be approved", async ({ page, request }) => {
  const { job } = await prepare(request);
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const panel = page.getByRole("region", { name: "Resume review and editing" });
  const advisory = panel.getByRole("region", { name: "Advisory factual review" });
  await expect(panel.getByLabel("Resume content budget")).toContainText("Within the estimated page budget");
  await expect(advisory).toContainText('AI review completed');
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByRole("button", { name: "Remove bullet 1", exact: true }).click();
  await panel.getByRole("group", { name: "Approved skills" }).getByLabel("Python", { exact: true }).uncheck();
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(advisory).toContainText('These findings apply to an earlier draft.');
  await expect(panel.getByRole('button', { name: 'Mark reviewed', exact: true })).toBeDisabled();
  await page.reload();
  await expect(advisory).toContainText('These findings apply to an earlier draft.');
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Add approved content", { exact: true }).selectOption("C-ALLOWED");
  await panel.getByRole("button", { name: "Add selected claim", exact: true }).click();
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel).toContainText('Detailed job coverage is separate from resume writing.');
  await expect(panel.getByRole("button", { name: "Mark reviewed", exact: true })).toBeEnabled();
});

test("resume review edits survive reload, invalidate review, and restore history", async ({ page, request }, info) => {
  const { job, run, url } = await prepare(request);
  let modelActions = 0;
  page.on("request", r => { if (r.method() === "POST" && (r.url().endsWith("/tailoring/resume") || r.url().includes("/api/ai/"))) modelActions++; });
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const panel = page.getByRole("region", { name: "Resume review and editing" });
  await panel.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await expect(panel.getByText("Reviewed — this exact saved version is approved.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Bullet 1", { exact: true }).fill("Successfully built an internal Python prototype.");
  const tabs = page.getByRole("navigation", { name: "Job views" });
  await tabs.getByRole("button", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Edit history", exact: true }).click();
  await page.getByLabel("New history note", { exact: true }).fill("Keep this unsaved application note");
  await captureWorkspace(page, info, "job-history-page.png");
  await tabs.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(panel.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await expect(panel.getByRole("button", { name: "Mark reviewed", exact: true })).toBeDisabled();
  await tabs.getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByLabel("New history note", { exact: true })).toHaveValue("Keep this unsaved application note");
  await tabs.getByRole("button", { name: "Overview", exact: true }).click();
  await captureWorkspace(page, info, "job-overview-page.png");
  await tabs.getByRole("button", { name: "Resume", exact: true }).click();
  await page.reload();
  await expect(panel.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await expect(panel.getByRole("button", { name: "Mark reviewed", exact: true })).toBeDisabled();
  await panel.screenshot({ path: info.outputPath("resume-editor.png") });
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  await panel.getByText("Changes and factual checks", { exact: true }).click();
  await expect(panel.getByText("Before", { exact: true }).first()).toBeVisible();
  await expect(panel.getByText("After", { exact: true }).first()).toBeVisible();
  await panel.screenshot({ path: info.outputPath("resume-comparison.png") });
  await panel.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await expect(panel.getByText("Reviewed — this exact saved version is approved.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Bullet 1", { exact: true }).fill("Invented production deployment with 90% revenue growth.");
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByText("Needs correction — resolve the saved validation issues.", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Mark reviewed", exact: true })).toBeDisabled();
  await panel.getByLabel("Resume revision history").selectOption(run.revision.id);
  await expect(panel.getByText("Historically reviewed — this is not the current eligible version.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Restore as new revision", exact: true }).click();
  await expect(panel.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await expect(panel.getByText("Reviewed — this exact saved version is approved.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(panel.getByLabel("Resume draft preview")).toContainText("Built an internal Python prototype.");
  const result = await (await request.get(url)).json();
  expect(result.history).toHaveLength(4); expect(result.approved_current).toBeTruthy(); expect(modelActions).toBe(0);
  expect(await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).toEqual(job);
});

test("resume concurrent editing keeps stale local work for explicit comparison", async ({ page, context, request }) => {
  const { job, url } = await prepare(request);
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const first = page.getByRole("region", { name: "Resume review and editing" });
  await first.getByRole("button", { name: "Edit resume", exact: true }).click();
  await first.getByLabel("Bullet 1", { exact: true }).fill("Successfully built an internal Python prototype.");
  const secondPage = await context.newPage();
  await secondPage.goto(`/jobs/${job.id}?tab=resume`);
  const second = secondPage.getByRole("region", { name: "Resume review and editing" });
  await expect(second.getByLabel("Bullet 1", { exact: true })).toBeVisible();
  await second.getByLabel("Bullet 1", { exact: true }).fill("Effectively built an internal Python prototype.");
  await second.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(second.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  // Saving in the second tab must not erase the first tab's recovery copy.
  await page.reload();
  await expect(first.getByText(/A newer revision exists/)).toBeVisible();
  await expect(first.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await first.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(first.getByRole("alert").filter({ hasText: "A newer revision was saved" })).toBeVisible();
  await first.getByLabel("I compared my edits with the current saved version.").check();
  await first.getByRole("button", { name: "Keep these edits on current version", exact: true }).click();
  await first.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(first.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  expect((await (await request.get(url)).json()).history).toHaveLength(3);
  await secondPage.close();
});

test("discard in one tab preserves another tab's unsaved resume after reload", async ({ page, context, request }) => {
  const { job } = await prepare(request);
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const first = page.getByRole("region", { name: "Resume review and editing" });
  await first.getByRole("button", { name: "Edit resume", exact: true }).click();
  await first.getByLabel("Bullet 1", { exact: true }).fill("Successfully built an internal Python prototype.");
  const other = await context.newPage();
  await other.goto(`/jobs/${job.id}?tab=resume`);
  const second = other.getByRole("region", { name: "Resume review and editing" });
  await second.getByLabel("Bullet 1", { exact: true }).fill("Effectively built an internal Python prototype.");
  await second.getByRole("button", { name: "Discard unsaved edits", exact: true }).click();
  await page.reload();
  await expect(first.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await other.reload();
  // A clean tab may recover the shared draft, but must not overwrite the other tab's copy.
  await page.reload();
  await expect(first.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await other.close();
});

test("resume lost save response retries once without duplicating revision", async ({ page, request }) => {
  const { job, url } = await prepare(request);
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const panel = page.getByRole("region", { name: "Resume review and editing" });
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Bullet 1", { exact: true }).fill("Successfully built an internal Python prototype.");
  let lost = false;
  await page.route("**/api/tailoring/resumes/*/revisions", async route => {
    if (!lost) { lost = true; await route.fetch(); await route.abort("failed"); } else await route.continue();
  });
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByRole("alert").filter({ hasText: "Your local edits are preserved" })).toBeVisible();
  await page.reload();
  await expect(panel.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  expect((await (await request.get(url)).json()).history).toHaveLength(2);
});

test("resume approved selection, discard and stale-source review stay explicit", async ({ page, request }) => {
  const { job, url } = await prepare(request);
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const panel = page.getByRole("region", { name: "Resume review and editing" });
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByRole("button", { name: "Remove bullet 1", exact: true }).click();
  await panel.getByLabel("Python", { exact: true }).uncheck();
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByText("Needs correction — resolve the saved validation issues.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Add approved content").selectOption("C-ALLOWED");
  await panel.getByRole("button", { name: "Add selected claim", exact: true }).click();
  await panel.getByLabel("Python", { exact: true }).check();
  await panel.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(panel.getByText("Awaiting review — automated checks passed.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await expect(panel.getByText("Reviewed — this exact saved version is approved.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Edit resume", exact: true }).click();
  await panel.getByLabel("Bullet 1", { exact: true }).fill("Unsaved invented wording");
  await panel.getByRole("button", { name: "Discard unsaved edits", exact: true }).click();
  await page.reload();
  await expect(panel.getByText("Reviewed — this exact saved version is approved.", { exact: true })).toBeVisible();
  await expect(panel.getByLabel("Resume draft preview")).not.toContainText("Unsaved invented wording");
  await request.patch(`${backend}/api/jobs/${job.id}`, { data: { source_content: "Different Python responsibilities." } });
  await panel.getByRole("button", { name: "Refresh resume", exact: true }).click();
  await expect(panel.getByText(/The job description or role changed/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Mark reviewed", exact: true })).toBeDisabled();
  const result = await (await request.get(url)).json();
  expect(result.approval).not.toBeNull(); expect(result.approved_current).toBeFalsy(); expect(result.history).toHaveLength(3);
});
