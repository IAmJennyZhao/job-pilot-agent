import { test, expect, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backend = "http://127.0.0.1:8100";

async function prepare(request: APIRequestContext, title: string) {
  const command = process.platform === "win32" ? "py" : "python";
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c", "import sys,json;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;print(json.dumps(import_payload()))"];
  const bundle = JSON.parse(execFileSync(command, args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.style_guide += ` generation ${Date.now()}`;
  const source = await (await request.post(`${backend}/api/profile/tailoring-sources/import`, { data: bundle })).json();
  const state = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  expect((await request.post(`${backend}/api/profile/tailoring-sources/${source.id}/activate`, { data: { expected_hash: source.bundle_hash, expected_active_id: state.active_id } })).ok()).toBeTruthy();
  return await (await request.post(`${backend}/api/jobs`, { data: { company: `Generation ${Date.now()}`, role_title: title, source_content: "Build reliable Python services. Collaborate with a team.", status: "Applied" } })).json();
}

test.afterEach(async ({ page }, info) => {
  if (info.status === "passed") {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.getByRole("region", { name: "Resume tailoring" }).screenshot({ path: info.outputPath("resume-workspace.png") });
  }
});

test("resume generation survives reload, shows evidence and preserves job state", async ({ page, request }) => {
  const job = await prepare(request, "Backend Engineer");
  let generations = 0, analysis = 0;
  page.on("request", r => { if (r.method() === "POST" && r.url().endsWith("/tailoring/resume")) generations++; if (r.method() === "POST" && r.url().includes("/api/ai/")) analysis++; });
  await page.goto(`/jobs/${job.id}?tailoring=prepare`);
  const panel = page.getByRole("region", { name: "Resume tailoring" });
  const generate = panel.getByRole("button", { name: "Generate tailored resume", exact: true });
  await expect(generate).toBeDisabled();
  expect(generations).toBe(0);
  await panel.getByLabel("I reviewed this complete saved job description.").check();
  await generate.click();
  await expect(panel.getByRole("button", { name: "Generating resume…", exact: true })).toBeDisabled();
  const tabs = page.getByRole("navigation", { name: "Job views" });
  await tabs.getByRole("button", { name: "Cover letter", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${backend}/api/jobs/${job.id}/tailoring`)).json()).runs.length).toBe(1);
  await page.reload();
  await expect(tabs.getByRole("button", { name: "Cover letter", exact: true })).toHaveAttribute("aria-pressed", "true");
  await tabs.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(panel.getByText("Resume run: completed", { exact: true })).toBeVisible();
  await expect(panel.getByLabel("Resume draft preview")).toContainText("Built an internal Python prototype.");
  await panel.getByText("Evidence for each bullet", { exact: true }).click();
  await expect(panel.getByText("Approved source C-ALLOWED", { exact: true })).toBeVisible();
  await expect(panel.getByText(/EXCLUDED_CLAIM_SECRET/)).toHaveCount(0);
  await page.reload();
  await expect(panel.getByLabel("Resume draft preview")).toBeVisible();
  expect(generations).toBe(1); expect(analysis).toBe(0);
  const after = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  expect(after).toEqual(job);
});

test("writer failure preserves a prior draft and supports explicit retry", async ({ page, request }) => {
  const job = await prepare(request, "AI Engineer");
  await page.goto(`/jobs/${job.id}?tab=resume`);
  const panel = page.getByRole("region", { name: "Resume tailoring" });
  await panel.getByLabel("I reviewed this complete saved job description.").check();
  await panel.getByRole("button", { name: "Generate tailored resume", exact: true }).click();
  await expect(panel.getByText("Resume run: completed", { exact: true })).toBeVisible();
  const first = (await (await request.get(`${backend}/api/jobs/${job.id}/tailoring`)).json()).runs[0].id;
  const preparation = panel.locator("#tailoring-preparation details").first();
  await expect(preparation).not.toHaveAttribute("open", "");
  await panel.getByRole("navigation", { name: "Resume workflow" }).getByRole("button", { name: "Preparation", exact: true }).click();
  await panel.getByRole("button", { name: "Edit full description", exact: true }).click();
  await panel.getByLabel("Full job description for tailoring").fill("Build Python services. SYNTHETIC_FAIL_ONCE");
  await preparation.locator(":scope > summary").click();
  await expect(panel.getByLabel("Full job description for tailoring")).toBeHidden();
  await panel.getByRole("navigation", { name: "Resume workflow" }).getByRole("button", { name: "Preparation", exact: true }).click();
  await expect(panel.getByLabel("Full job description for tailoring")).toHaveValue("Build Python services. SYNTHETIC_FAIL_ONCE");
  await panel.getByRole("button", { name: "Save description", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Edit full description", exact: true })).toBeVisible();
  await panel.getByLabel("I reviewed this complete saved job description.").check();
  await panel.getByRole("button", { name: "Generate tailored resume", exact: true }).click();
  await expect(panel.getByText("Resume run: failed", { exact: true })).toBeVisible();
  await expect(panel.getByText(/Synthetic provider timeout/).first()).toBeVisible();
  expect((await (await request.get(`${backend}/api/tailoring/runs/${first}`)).json()).revision).not.toBeNull();
  await panel.getByRole("button", { name: "Retry from saved checkpoints", exact: true }).click();
  await expect(panel.getByText("Resume run: completed", { exact: true })).toBeVisible();
  const all = (await (await request.get(`${backend}/api/jobs/${job.id}/tailoring`)).json()).runs;
  expect(all).toHaveLength(3);
  const newest = await (await request.get(`${backend}/api/tailoring/runs/${all[0].id}`)).json();
  expect(newest.stages.map((s: { stage: string }) => s.stage)).toEqual(['write', 'review']);
  await panel.getByLabel("Resume generation history").selectOption(first);
  await expect(panel.getByText(/Sources or the job changed after this run/)).toBeVisible();
  await expect(panel.getByLabel("Resume draft preview")).toBeVisible();
});
