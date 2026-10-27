import { expect, test, type APIRequestContext, type Locator, type Page, type TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backend = "http://127.0.0.1:8100";

async function source(request: APIRequestContext, activate = false) {
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c", "import sys,json;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;print(json.dumps(import_payload()))"];
  const bundle = JSON.parse(execFileSync(process.platform === "win32" ? "py" : "python", args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.bank_markdown = bundle.bank_markdown.replace("bank_version: synthetic.1", `bank_version: readiness.${crypto.randomUUID().slice(0, 8)}`);
  const imported = await request.post(`${backend}/api/profile/tailoring-sources/import`, { data: bundle });
  expect(imported.ok()).toBeTruthy();
  const result = await imported.json();
  if (activate) await activateSource(request, result);
  return result;
}

async function activateSource(request: APIRequestContext, version: { id: string; bundle_hash: string }) {
  const state = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  const response = await request.post(`${backend}/api/profile/tailoring-sources/${version.id}/activate`, { data: { expected_hash: version.bundle_hash, expected_active_id: state.active_id } });
  expect(response.ok()).toBeTruthy();
}

async function capture(page: Page, info: TestInfo, name: string, area: Locator) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  const bounds = await area.boundingBox();
  if (!bounds) throw new Error("Review capture must be visible.");
  await page.screenshot({ path: info.outputPath(name), fullPage: true, clip: bounds, style: "nextjs-portal { display: none !important; }" });
}

test.afterEach(async ({ page }) => {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
});

test("library completeness and manual readiness never activate or update source facts", async ({ page, request }, info) => {
  const active = await source(request, true);
  const before = await (await request.get(`${backend}/api/profile/tailoring-sources/${active.id}`)).json();
  const option = await request.post(`${backend}/api/profile/resume-options`, { data: { title: `Reusable ${Date.now()}`, parsed_text: "Reusable candidate information.", status: "draft" } });
  expect(option.ok()).toBeTruthy();
  const created = await option.json();
  await page.route("**/api/profile/cover-letter-templates", route => route.fulfill({ json: [] }));
  let sourceWrites = 0;
  page.on("request", req => { if (req.method() === "POST" && req.url().includes("/tailoring-sources/")) sourceWrites++; });
  await page.goto("/profile?tab=resumes");
  await expect(page.getByText("Reusable asset completeness", { exact: true })).toBeVisible();
  await expect(page.getByText("Ready for job review", { exact: true })).toHaveCount(0);
  const optional = page.getByRole("button", { name: "Cover template (optional)", exact: true });
  await expect(optional).toHaveAttribute("title", "Optional style template; letters can be generated without one");
  const summary = page.getByRole("complementary", { name: "Active tailoring source" });
  await expect(summary).toHaveAttribute("data-source-id", active.id);
  const library = page.getByRole("region", { name: "Reusable resumes", exact: true });
  const card = library.locator("section").filter({ has: page.getByRole("heading", { name: created.title, exact: true }) });
  const edit = card.getByRole("button", { name: "Edit", exact: true });
  if (await edit.count()) await edit.click();
  await expect(library.getByRole("textbox", { name: "Title", exact: true })).toHaveValue(created.title);
  await expect(library.getByRole("combobox", { name: "Library status", exact: true })).toHaveValue("draft");
  await expect(page.getByRole("button", { name: "Resume content", exact: true })).toHaveAttribute("title", "Resume content: saved content available");
  await library.getByText("Merge and library actions", { exact: true }).click();
  await library.getByRole("button", { name: "Save, mark ready & merge into Base profile", exact: true }).click();
  await expect(library.getByRole("combobox", { name: "Library status", exact: true })).toHaveValue("ready");
  await expect(page.getByText(/manually marked ready for selection/)).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Application asset views" });
  await tabs.getByRole("button", { name: "Base profile", exact: true }).click();
  const base = page.getByRole("region", { name: "Base profile", exact: true });
  await base.getByLabel("Name", { exact: true }).fill("Reusable profile correction");
  await base.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(base.getByText("Saved successfully.", { exact: true })).toBeVisible();
  await summary.getByText("Source boundaries and identifiers", { exact: true }).click();
  await expect(summary.getByText(/Profile edits, resume merges and library status changes do not update or activate/)).toBeVisible();
  await summary.getByText("Source boundaries and identifiers", { exact: true }).click();
  expect(await (await request.get(`${backend}/api/profile/tailoring-sources/${active.id}`)).json()).toEqual(before);
  expect((await (await request.get(`${backend}/api/profile/tailoring-sources`)).json()).active_id).toBe(active.id);
  expect(sourceWrites).toBe(0);
  await capture(page, info, "asset-completeness.png", page.locator("section").filter({ has: page.getByText("Reusable asset completeness", { exact: true }) }));
  await capture(page, info, "assets-summary.png", summary);
});

test("active source summary stays separate from pending selection and activation conflicts", async ({ page, request }, info) => {
  const first = await source(request, true);
  const pending = await source(request);
  await page.goto("/profile?tab=sources");
  const summary = page.getByRole("complementary", { name: "Active tailoring source" });
  const manager = page.getByRole("region", { name: "Tailoring sources", exact: true });
  await expect(summary).toHaveAttribute("data-source-id", first.id);
  await manager.getByLabel("Source version", { exact: true }).selectOption(pending.id);
  await expect(manager.getByText("Source status: pending", { exact: true })).toBeVisible();
  await expect(summary).toHaveAttribute("data-source-id", first.id);
  await expect(manager.getByText(/It is not used for new generations until explicitly activated/)).toBeVisible();
  const activate = manager.getByRole("button", { name: "Activate reviewed sources", exact: true });
  await expect(activate).toBeDisabled();
  await capture(page, info, "pending-version.png", page.locator("#main-content"));
  const reviewed = manager.getByLabel("I reviewed this version's facts, exclusions, preferences, and layout sources.");
  await reviewed.check();
  const concurrent = await source(request, true);
  await activate.click();
  await expect(manager.getByRole("alert")).toContainText("Active source changed");
  await expect(summary).toHaveAttribute("data-source-id", concurrent.id);
  await expect(reviewed).not.toBeChecked();
  await expect(activate).toBeDisabled();
  expect((await (await request.get(`${backend}/api/profile/tailoring-sources/${pending.id}`)).json()).status).toBe("pending");
  await reviewed.check();
  await activate.click();
  await expect(manager.getByText("Source status: active", { exact: true })).toBeVisible();
  await expect(summary).toHaveAttribute("data-source-id", pending.id);
  await manager.getByText("Activation history", { exact: true }).click();
  await expect(manager.getByText(/^active ·/)).toBeVisible();
  await manager.getByRole("button", { name: "Revoke this version", exact: true }).click();
  await expect(manager.getByText("Source status: revoked", { exact: true })).toBeVisible();
  await expect(summary).toHaveAttribute("data-source-id", "");
  await expect(summary.getByText("No active bundle", { exact: true })).toBeVisible();
  await expect(manager.getByRole("button", { name: "Activate reviewed sources" })).toHaveCount(0);
  await capture(page, info, "no-active-source.png", summary);
});

test("generation prerequisites and saved review eligibility stay separate with no letter template", async ({ page, request }, info) => {
  const active = await source(request, true);
  const response = await request.post(`${backend}/api/jobs`, { data: { company: `Readiness ${Date.now()}`, role_title: "Backend Engineer", source_content: "Build reliable Python services. Collaborate with a team.", status: "Saved" } });
  expect(response.ok()).toBeTruthy();
  const job = await response.json();
  await page.route(`**/api/jobs/${job.id}/cover-letters`, async route => {
    if (route.request().method() !== "GET") return route.continue();
    const result = await route.fetch();
    await route.fulfill({ response: result, json: { ...await result.json(), templates: [] } });
  });
  const generations: Array<{ options: { template_id: string | null } }> = [];
  page.on("request", req => { if (req.method() === "POST" && req.url().endsWith(`/jobs/${job.id}/cover-letters`)) generations.push(req.postDataJSON()); });
  await page.goto(`/jobs/${job.id}?tab=overview`);
  await expect(page.getByText("Analysis can run", { exact: true })).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Job views" });
  await tabs.getByRole("button", { name: "Resume", exact: true }).click();
  const resume = page.getByRole("region", { name: "Resume tailoring", exact: true });
  await expect(resume.getByRole("complementary", { name: "Active tailoring source" })).toHaveAttribute("data-source-id", active.id);
  await expect(resume.getByText(/Generation prerequisites: inputs available/)).toBeVisible();
  await expect(resume.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeDisabled();
  await capture(page, info, "resume-preparation.png", page.locator("#tailoring-preparation"));
  await tabs.getByRole("button", { name: "Cover letter", exact: true }).click();
  const letter = page.getByRole("region", { name: "Cover letters", exact: true });
  await expect(letter.getByRole("complementary", { name: "Active tailoring source" })).toHaveAttribute("data-source-id", active.id);
  await expect(letter.getByLabel("Letter style template (optional)", { exact: true }).locator("option")).toHaveCount(1);
  const generate = letter.getByRole("button", { name: "Generate tailored cover letters", exact: true });
  await expect(generate).toBeDisabled();
  await letter.getByLabel("I reviewed the full saved posting for this letter.").check();
  await expect(generate).toBeEnabled();
  expect(generations).toHaveLength(0);
  await capture(page, info, "letter-preparation.png", page.locator("#letter-preparation"));
  await generate.click();
  await expect(letter.getByText("Letter run: completed", { exact: true })).toBeVisible();
  expect(generations).toHaveLength(1);
  expect(generations[0].options.template_id).toBeNull();
  await expect(letter.locator('[aria-label="Saved letter review eligibility"]')).toContainText("eligible for content review");
  await expect(letter.getByRole("button", { name: "Approve exact letter revision", exact: true })).toBeDisabled();
  await expect(letter.getByRole("button", { name: "Download letter TXT", exact: true })).toBeDisabled();
  expect((await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).status).toBe("Saved");
});
