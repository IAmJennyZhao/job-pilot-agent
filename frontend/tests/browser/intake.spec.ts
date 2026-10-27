import { test, expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const backend = "http://127.0.0.1:8100";
const description = "  Synthetic Backend Engineer\n\nUSD 100000-120000 annual base salary; NYC salary band.\nRemote anywhere including NYC. Minimum 2 years required.\n  ";

async function captureIntake(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  const bounds = await page.locator("#job-intake").boundingBox();
  if (!bounds) throw new Error("Intake must be visible for its review capture.");
  await page.screenshot({ path: info.outputPath(name), fullPage: true, clip: bounds, style: "nextjs-portal { display: none !important; }" });
}

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

for (const [label, status] of [["Save", "Saved"], ["Apply", "Applied"], ["Tailor resume", "Saved"], ["Archive", "Archived"]]) {
  test(`intake ${label} persists the explicit decision above Summary`, async ({ page, request }, info) => {
    const company = `Intake ${label} ${info.project.name} ${Date.now()}`;
    let generationCalls = 0;
    page.on("request", req => { if (req.method() === "POST" && (/\/api\/ai\//.test(req.url()) || /\/tailoring\/resume$|\/cover-letters$/.test(req.url()))) generationCalls++; });
    await page.goto("/jobs?tab=tracker");
    await expect(page.getByRole("navigation", { name: "Jobs views" })).toHaveCount(0);
    await page.getByRole("button", { name: "Add job", exact: true }).click();
    await page.getByLabel("Pasted page content").fill(description);
    await page.getByRole("button", { name: "Manual entry", exact: true }).click();
    const decisions = page.getByRole("group", { name: "Job decisions" });
    await expect(decisions.getByRole("button")).toHaveCount(4);
    await expect(decisions.getByRole("button", { name: label, exact: true })).toBeDisabled();
    await page.getByLabel("Company", { exact: true }).fill(company);
    await page.getByLabel("Role title", { exact: true }).fill("Engineer");
    const action = decisions.getByRole("button", { name: label, exact: true });
    await expect(action).toBeEnabled();
    const toolbarBox = (await decisions.boundingBox())!;
    const summaryBox = (await page.getByLabel("Summary", { exact: true }).boundingBox())!;
    expect(toolbarBox.y + toolbarBox.height).toBeLessThan(summaryBox.y);
    if (label === "Save") await captureIntake(page, info, "intake-decisions.png");
    await action.click();
    if (label === "Tailor resume") {
      await expect(page).toHaveURL(/tailoring=prepare#tailoring-preparation/);
      await expect(page.getByRole("heading", { name: "Tailoring preparation", exact: true })).toBeVisible();
    } else await expect(page.getByRole("link", { name: "Open saved job", exact: true })).toBeVisible();
    const jobs = await (await request.get(`${backend}/api/jobs?include_archived=true`)).json();
    const saved = jobs.filter((job: { company: string }) => job.company === company);
    expect(saved).toHaveLength(1);
    expect(saved[0].status).toBe(status);
    expect(generationCalls).toBe(0);
    await page.reload();
    if (label === "Tailor resume") await expect(page.getByRole("heading", { name: "Tailoring preparation", exact: true })).toBeVisible();
    expect((await (await request.get(`${backend}/api/jobs/${saved[0].id}`)).json()).status).toBe(status);
  });
}

test("intake extracts basics, preserves reload draft and continues despite red salary", async ({ page, request }, info) => {
  await activate(request);
  let extractionCalls = 0, analysisCalls = 0, generationCalls = 0;
  page.on("request", r => { if (r.url().includes("extract-preview")) extractionCalls++; if (r.method() === "POST" && r.url().includes("/api/ai/")) analysisCalls++; if (r.method() === "POST" && /\/tailoring\/resume$|\/cover-letters$/.test(r.url())) generationCalls++; });
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByLabel("Job URL", { exact: true }).fill(`https://example.test/${info.project.name}-${Date.now()}`);
  await page.getByLabel("Pasted page content").fill(description);
  await page.getByRole("button", { name: "Extract fields", exact: true }).click();
  await expect(page.getByLabel("Company", { exact: true })).toHaveValue("Synthetic Intake Employer");
  await page.getByLabel("Role title", { exact: true }).fill(`Engineer ${Date.now()}`);
  await expect(page.getByText(/Base pay is below your USD 135,000 target/)).toBeVisible();
  await expect(page.getByLabel("Pasted page content")).toBeHidden();
  await expect(page.getByLabel("Pay minimum", { exact: true })).toBeHidden();
  await captureIntake(page, info, "intake-review.png");
  await page.getByText("Preference details and evidence", { exact: true }).click();
  await expect(page.getByText(/Work arrangement permits living in NYC/)).toBeVisible();
  await captureIntake(page, info, "intake-preferences.png");
  await page.getByText("Preference details and evidence", { exact: true }).click();
  await page.getByText("Review or correct preference facts", { exact: true }).click();
  await page.getByLabel("Can live in NYC", { exact: true }).selectOption("no");
  await expect(page.getByText(/Work arrangement does not permit living in NYC/)).toBeVisible();
  await page.getByLabel("Can live in NYC", { exact: true }).selectOption("yes");
  await page.getByLabel("I reviewed the full job description for later tailoring.").check();
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByLabel("Pasted page content")).toHaveValue(description);
  await expect(page.getByText(/Base pay is below your USD 135,000 target/)).toBeVisible();
  await captureIntake(page, info, "review-flags.png");
  await page.getByRole("button", { name: "Tailor resume", exact: true }).click();
  await expect(page).toHaveURL(/\/jobs\/.+tailoring=prepare/);
  await expect(page.getByRole("heading", { name: "Tailoring preparation" })).toBeVisible();
  await expect(page.getByText("Full job description reviewed.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeVisible();
  expect(extractionCalls).toBe(1); expect(analysisCalls).toBe(0); expect(generationCalls).toBe(0);
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
  await page.getByText("Posting source and extraction", { exact: true }).click();
  await page.getByLabel("Pasted page content").fill(description + " Changed restrictions.");
  await expect(page.getByText(/The source changed or this is an older draft/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Tailor resume", exact: true })).toBeDisabled();
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
  const payloads: Array<{ request_key: string; expected_evaluation_hash: string }> = [];
  await page.route("**/api/jobs/intake/save", async route => {
    saves++;
    payloads.push(route.request().postDataJSON());
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
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /fetch|network/i })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByText("Possible duplicates — open the saved job to continue there:")).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open saved job" })).toBeVisible();
  const jobs = await (await request.get(`${backend}/api/jobs`)).json();
  expect(jobs.filter((job: { company: string }) => job.company === company)).toHaveLength(1);
  expect(saves).toBe(2);
  expect(payloads[1].request_key).toBe(payloads[0].request_key);
  expect(payloads[1].expected_evaluation_hash).toBe(payloads[0].expected_evaluation_hash);
});

test("intake disclosures preserve corrections and reveal recovered validation errors", async ({ page, request }, info) => {
  const company = `Corrections ${info.project.name} ${Date.now()}`;
  const sourceUrl = `https://example.test/corrections/${Date.now()}`;
  let saves = 0;
  page.on("request", req => { if (req.method() === "POST" && req.url().endsWith("/intake/save")) saves++; });
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await captureIntake(page, info, "intake-start.png");
  await page.getByLabel("Job URL", { exact: true }).fill(sourceUrl);
  await page.getByLabel("Pasted page content").fill(description);
  await page.getByRole("button", { name: "Manual entry", exact: true }).click();
  await page.getByLabel("Company", { exact: true }).fill(company);
  await page.getByLabel("Role title", { exact: true }).fill("Backend Engineer");
  await page.locator("#job-intake summary").filter({ hasText: /^Pay/ }).click();
  await page.getByLabel("Pay minimum", { exact: true }).fill("200000");
  await page.getByLabel("Pay maximum", { exact: true }).fill("100000");
  await expect(page.getByText("Maximum pay must be at least the minimum.", { exact: true })).toBeVisible();
  await page.getByText(/^Posting and other links/).click();
  await page.getByLabel("Link 1 URL", { exact: true }).fill("ftp://example.test/posting");
  await page.getByText("Additional job details", { exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.getByLabel("Notes", { exact: true }).fill("Keep these advanced corrections.");
  await page.getByText("Additional job details", { exact: true }).click();
  await page.getByRole("button", { name: "Hide add job", exact: true }).click();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByLabel("Pay minimum", { exact: true })).toHaveValue("200000");
  await page.reload();
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await expect(page.getByLabel("Pay maximum", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Link 1 URL", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
  await captureIntake(page, info, "intake-corrections.png");
  await page.getByLabel("Pay maximum", { exact: true }).fill("220000");
  await page.getByLabel("Link 1 URL", { exact: true }).fill(sourceUrl);
  await page.getByText("Additional job details", { exact: true }).click();
  await expect(page.getByLabel("Notes", { exact: true })).toHaveValue("Keep these advanced corrections.");
  expect(saves).toBe(0);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open saved job", exact: true })).toBeVisible();
  const record = (await (await request.get(`${backend}/api/jobs`)).json()).find((job: { company: string }) => job.company === company);
  const saved = await (await request.get(`${backend}/api/jobs/${record.id}`)).json();
  expect(saved).toMatchObject({ status: "Saved", pay_min: 200000, pay_max: 220000, notes: "Keep these advanced corrections.", source_content: description });
  expect(saved.links.some((link: { url: string }) => link.url === sourceUrl)).toBeTruthy();
  expect(saves).toBe(1);
});

test("intake duplicate confirmation remains explicit before creating a separate posting", async ({ page, request }, info) => {
  const company = `Duplicate ${info.project.name} ${Date.now()}`;
  const existing = await request.post(`${backend}/api/jobs`, { data: { company, role_title: "Backend Engineer", status: "Saved" } });
  expect(existing.ok()).toBeTruthy();
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Add job", exact: true }).click();
  await page.getByRole("button", { name: "Manual entry", exact: true }).click();
  await page.getByLabel("Company", { exact: true }).fill(company);
  await page.getByLabel("Role title", { exact: true }).fill("Backend Engineer");
  await expect(page.getByText("Possible duplicates — open the saved job to continue there:")).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /matching job is already saved/i })).toBeVisible();
  const matches = async () => (await (await request.get(`${backend}/api/jobs`)).json()).filter((job: { company: string }) => job.company === company);
  expect(await matches()).toHaveLength(1);
  await page.getByLabel("This is a separate posting; save another job.").check();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open saved job", exact: true })).toBeVisible();
  expect(await matches()).toHaveLength(2);
});
