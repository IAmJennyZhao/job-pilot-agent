import { test, expect, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backend = "http://127.0.0.1:8100";
const description = "  Synthetic Backend Engineer\n\nUSD 100000-120000 annual base salary; NYC salary band.\nRemote anywhere including NYC. Minimum 2 years required.\n  ";

test("incompatible intake recovery preserves exact bytes and another tab's draft", async ({ page, context }, info) => {
  const key = "job-pilot:draft:job-intake";
  const raw = '{"source_content":"unfinished legacy draft';
  await page.goto("/jobs");
  await page.evaluate(({ key, raw }) => { localStorage.setItem(key, raw); sessionStorage.setItem(key, raw); }, { key, raw });
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByText("The saved job intake has an incompatible format.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Extract fields", exact: true })).toBeDisabled();
  expect(await page.evaluate(key => localStorage.getItem(key), key)).toBe(raw);
  const event = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download job intake recovery", exact: true }).click();
  const filename = info.outputPath("intake-recovery.json"); await (await event).saveAs(filename);
  const { readFile } = await import("node:fs/promises");
  expect(await readFile(filename, "utf8")).toBe(raw);
  const other = await context.newPage();
  await other.goto("/jobs");
  await other.getByRole("button", { name: "Add job", exact: true }).click();
  await other.getByRole("button", { name: "Discard incompatible job intake", exact: true }).click();
  await other.getByLabel("Pasted page content").fill("Other tab's unfinished posting");
  await expect.poll(() => other.evaluate(key => localStorage.getItem(key), key)).toContain("Other tab");
  await page.getByRole("button", { name: "Discard incompatible job intake", exact: true }).click();
  await other.reload();
  await other.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(other.getByLabel("Pasted page content")).toHaveValue("Other tab's unfinished posting");
  await other.close();
});

async function activate(request: APIRequestContext) {
  const command = process.platform === "win32" ? "py" : "python";
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c", "import sys,json,yaml;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;from test_intake_preferences import preferences;p=import_payload();p['preferences_yaml']=yaml.safe_dump(preferences().model_dump(by_alias=True));print(json.dumps(p))"];
  const bundle = JSON.parse(execFileSync(command, args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.style_guide += ` ${Date.now()}`;
  const source = await (await request.post(`${backend}/api/profile/tailoring-sources/import`, { data: bundle })).json();
  const current = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  const result = await request.post(`${backend}/api/profile/tailoring-sources/${source.id}/activate`, { data: { expected_hash: source.bundle_hash, expected_active_id: current.active_id } });
  expect(result.ok()).toBeTruthy();
  return source;
}

test.afterEach(async ({ page }, info) => {
  if (info.status === "passed") {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: info.outputPath("intake-verified.png"), fullPage: true });
  }
});

test("intake extracts basics, preserves reload draft and continues despite red salary", async ({ page, request }, info) => {
  await activate(request);
  let extractionCalls = 0, analysisCalls = 0;
  page.on("request", r => { if (r.url().includes("extract-preview")) extractionCalls++; if (r.method() === "POST" && r.url().includes("/api/ai/")) analysisCalls++; });
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByLabel("Job URL", { exact: true }).fill(`https://example.test/${info.project.name}-${Date.now()}`);
  await page.getByLabel("Pasted page content").fill(description);
  await page.getByRole("button", { name: "Extract fields", exact: true }).click();
  await expect(page.getByLabel("Company", { exact: true })).toHaveValue("Synthetic Intake Employer");
  await page.getByLabel("Role title", { exact: true }).fill(`Engineer ${Date.now()}`);
  await expect(page.getByText(/Base pay is below your USD 135,000 target/)).toBeVisible();
  await page.getByText("Review or correct preference facts", { exact: true }).click();
  await page.getByLabel("Can live in NYC", { exact: true }).selectOption("no");
  await expect(page.getByText(/Work arrangement does not permit living in NYC/)).toBeVisible();
  await page.getByLabel("Can live in NYC", { exact: true }).selectOption("yes");
  await page.getByLabel("I reviewed the full job description for later tailoring.").check();
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByLabel("Pasted page content")).toHaveValue(description);
  await expect(page.getByText(/Base pay is below your USD 135,000 target/)).toBeVisible();
  await page.locator("#job-intake").screenshot({ path: info.outputPath("review-flags.png") });
  await page.getByRole("button", { name: "Continue to tailoring", exact: true }).click();
  await expect(page).toHaveURL(/\/jobs\/.+tailoring=prepare/);
  await expect(page.getByRole("heading", { name: "Tailoring preparation" })).toBeVisible();
  await expect(page.getByText("Full job description reviewed.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeVisible();
  expect(extractionCalls).toBe(1); expect(analysisCalls).toBe(0);
  const id = new URL(page.url()).pathname.split("/").pop();
  const saved = await (await request.get(`${backend}/api/jobs/${id}`)).json();
  expect(saved.status).toBe("Saved"); expect(saved.source_content).toBe(description);
});

test("intake source edits invalidate review and Not pursuing discards without writes", async ({ page, request }) => {
  const before = await (await request.get(`${backend}/api/jobs?include_archived=true`)).json();
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByLabel("Pasted page content").fill(description);
  await page.getByRole("button", { name: "Extract fields", exact: true }).click();
  await expect(page.getByLabel("Company", { exact: true })).toHaveValue("Synthetic Intake Employer");
  await page.getByLabel("Pasted page content").fill(description + " Changed restrictions.");
  await expect(page.getByText(/The source changed or this is an older draft/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue to tailoring", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Not pursuing", exact: true }).click();
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByLabel("Pasted page content")).toHaveValue("");
  expect(await (await request.get(`${backend}/api/jobs?include_archived=true`)).json()).toEqual(before);
});

test("intake manual recovery retries a lost save response once and shows duplicates", async ({ page, request }, info) => {
  await page.route("**/api/jobs/extract-preview", route => route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic extraction failure; use manual entry." }) }));
  const company = `Retry ${info.project.name} ${Date.now()}`;
  let saves = 0;
  await page.route("**/api/jobs/intake/save", async route => {
    saves++;
    if (saves === 1) { await route.fetch(); await route.abort("failed"); }
    else await route.continue();
  });
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByLabel("Pasted page content").fill(description);
  await page.getByRole("button", { name: "Extract fields", exact: true }).click();
  await page.getByRole("button", { name: "Use manual fallback", exact: true }).click();
  await page.getByLabel("Company", { exact: true }).fill(company);
  await page.getByLabel("Role title", { exact: true }).fill("Backend Engineer");
  await page.getByRole("button", { name: "Save for later", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /fetch|network/i })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByText("Possible duplicates — open the saved job to continue there:")).toBeVisible();
  await page.getByRole("button", { name: "Save for later", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open saved job" })).toBeVisible();
  const jobs = await (await request.get(`${backend}/api/jobs`)).json();
  expect(jobs.filter((job: { company: string }) => job.company === company)).toHaveLength(1);
  expect(saves).toBe(2);
});
