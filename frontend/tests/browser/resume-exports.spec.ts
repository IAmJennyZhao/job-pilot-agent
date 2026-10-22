import { test, expect, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

const backend = "http://127.0.0.1:8100";
async function prepare(request: APIRequestContext) {
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c", "import sys,json;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;print(json.dumps(import_payload()))"];
  const bundle = JSON.parse(execFileSync(process.platform === "win32" ? "py" : "python", args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.style_guide += ` exports ${Date.now()}`;
  const source = await (await request.post(`${backend}/api/profile/tailoring-sources/import`, { data: bundle })).json();
  const state = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  expect((await request.post(`${backend}/api/profile/tailoring-sources/${source.id}/activate`, { data: { expected_hash: source.bundle_hash, expected_active_id: state.active_id } })).ok()).toBeTruthy();
  const job = await (await request.post(`${backend}/api/jobs`, { data: { company: `Exports ${Date.now()}`, role_title: "Backend Engineer", source_content: "Build Python services.", status: "Saved" } })).json();
  const { readiness } = await (await request.get(`${backend}/api/jobs/${job.id}/tailoring`)).json();
  const run = await (await request.post(`${backend}/api/jobs/${job.id}/tailoring/resume`, { data: { request_key: crypto.randomUUID(), expected_input_hash: readiness.input_hash, reviewed_description_hash: readiness.description_hash, acknowledged_evaluation_hash: readiness.evaluation.evaluation_hash } })).json();
  expect(run.state).toBe("completed");
  return { job, source, run, url: `${backend}/api/tailoring/resumes/${run.revision.id}` };
}

test("lost render response and export failures recover the same saved artifact", async ({ page, request }, info) => {
  const { job, url, run } = await prepare(request);
  let models = 0, lost = false;
  page.on("request", r => { if (r.method() === "POST" && /tailoring\/resume$|\/api\/ai\//.test(r.url())) models++; });
  await page.route("**/api/tailoring/resumes/*/renders", async route => {
    if (route.request().method() === "POST" && !lost) { lost = true; await route.fetch(); await route.abort("failed"); }
    else await route.continue();
  });
  await page.goto(`/jobs/${job.id}`);
  const review = page.getByRole("region", { name: "Resume review and editing" });
  const exports = page.getByRole("region", { name: "Resume rendering and downloads" });
  await review.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await exports.getByRole("button", { name: "Render saved revision", exact: true }).click();
  await expect(exports.getByRole("alert")).toContainText(/fetch|network/i);
  await page.reload();
  await exports.getByRole("button", { name: "Render saved revision", exact: true }).click();
  await exports.getByRole("button", { name: "Open PDF preview", exact: true }).click();
  await exports.getByLabel("I inspected this exact PDF and approve its layout.").check();
  await exports.getByRole("button", { name: "Approve final exports", exact: true }).click();
  await expect(exports.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
  const renders = await (await request.get(url + `/renders?revision_id=${run.revision.id}`)).json();
  expect(renders).toHaveLength(1);
  let attempts = 0;
  await page.route("**/api/tailoring/resumes/*/renders/*/download/pdf", route => {
    attempts++;
    if (attempts === 1) return route.fulfill({ status: 503, contentType: "text/html", body: "<html>Proxy unavailable</html>" });
    if (attempts === 2) return route.abort("failed");
    if (attempts === 3) return route.fulfill({ status: 200, contentType: "application/pdf", body: "" });
    return route.continue();
  });
  for (let i = 0; i < 3; i++) {
    await exports.getByRole("button", { name: "Download PDF", exact: true }).click();
    await expect(exports.getByRole("alert")).toContainText("Retry from this saved version.");
  }
  const event = page.waitForEvent("download");
  await exports.getByRole("button", { name: "Download PDF", exact: true }).click();
  const file = info.outputPath("recovered.pdf"); await (await event).saveAs(file);
  expect(createHash("sha256").update(await readFile(file)).digest("hex")).toBe(renders[0].hashes.pdf);
  await page.evaluate(() => { Object.defineProperty(navigator.clipboard, "writeText", { value: async () => { throw new Error("Clipboard permission denied"); } }); });
  await exports.getByRole("button", { name: "Copy approved text", exact: true }).click();
  await expect(exports.getByRole("alert")).toContainText("Clipboard permission denied");
  await expect(exports.getByRole("button", { name: "Download text", exact: true })).toBeEnabled();
  expect(models).toBe(0);
  expect(await (await request.get(url + `/renders?revision_id=${run.revision.id}`)).json()).toEqual(renders);
});

test("preview, final approval, exact downloads and historical exports", async ({ page, request }, info) => {
  const { job, source, run, url } = await prepare(request);
  let modelRequests = 0;
  page.on("request", r => { if (r.method() === "POST" && (r.url().endsWith("/tailoring/resume") || r.url().includes("/api/ai/"))) modelRequests++; });
  await page.goto(`/jobs/${job.id}`);
  const review = page.getByRole("region", { name: "Resume review and editing" });
  const exports = page.getByRole("region", { name: "Resume rendering and downloads" });
  await review.getByRole("button", { name: "Mark reviewed", exact: true }).click();
  await exports.getByRole("button", { name: "Render saved revision", exact: true }).click();
  await expect(exports.getByText("1 page · Draft preview", { exact: true })).toBeVisible();
  await expect(exports.getByRole("button", { name: "Download PDF", exact: true })).toHaveCount(0);
  await exports.getByRole("button", { name: "Open PDF preview", exact: true }).click();
  await expect(exports.getByRole("img", { name: "Rendered resume page 1" })).toBeVisible();
  await expect(exports.getByRole("button", { name: "Approve final exports", exact: true })).toBeDisabled();
  await exports.getByLabel("I inspected this exact PDF and approve its layout.").check();
  await exports.screenshot({ path: info.outputPath("resume-pdf-preview.png") });
  await exports.getByRole("button", { name: "Approve final exports", exact: true }).click();
  await expect(exports.getByText("1 page · Final approved export", { exact: true })).toBeVisible();
  const render = (await (await request.get(url + `/renders?revision_id=${run.revision.id}`)).json())[0];
  for (const [label, format] of [["PDF", "pdf"], ["TeX", "tex"], ["text", "txt"]]) {
    const event = page.waitForEvent("download");
    await exports.getByRole("button", { name: `Download ${label}`, exact: true }).click();
    const download = await event;
    const filename = info.outputPath(`approved.${format}`);
    await download.saveAs(filename);
    expect(createHash("sha256").update(await readFile(filename)).digest("hex")).toBe(render.hashes[format]);
  }
  await page.reload();
  await expect(exports.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
  await review.getByRole("button", { name: "Edit resume", exact: true }).click();
  await review.getByLabel("Bullet 1", { exact: true }).fill("Successfully built an internal Python prototype.");
  await page.reload();
  await expect(review.getByLabel("Bullet 1", { exact: true })).toHaveValue("Successfully built an internal Python prototype.");
  await expect(exports.getByRole("button", { name: "Render saved revision", exact: true })).toBeDisabled();
  await review.getByRole("button", { name: "Save and validate", exact: true }).click();
  await expect(exports.getByText("No PDF has been rendered for this saved revision.")).toBeVisible();
  await review.getByLabel("Resume revision history").selectOption(run.revision.id);
  await expect(exports.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
  expect((await request.post(`${backend}/api/profile/tailoring-sources/${source.id}/revoke`, { data: { expected_hash: source.bundle_hash, expected_active_id: source.id } })).ok()).toBeTruthy();
  await page.reload();
  await review.getByLabel("Resume revision history").selectOption(run.revision.id);
  await expect(review.getByText(/source bundle was revoked/)).toBeVisible();
  await expect(exports.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
  expect((await request.get(url + `/renders/${render.id}/download/pdf`)).ok()).toBeTruthy();
  expect(modelRequests).toBe(0);
  expect(await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).toEqual(job);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
});

test("unapproved preview removal and content review cannot bypass final approval", async ({ page, request }) => {
  const { job, run, url } = await prepare(request);
  await page.goto(`/jobs/${job.id}`);
  const exports = page.getByRole("region", { name: "Resume rendering and downloads" });
  await exports.getByRole("button", { name: "Render saved revision", exact: true }).click();
  await exports.getByRole("button", { name: "Open PDF preview", exact: true }).click();
  await exports.getByLabel("I inspected this exact PDF and approve its layout.").check();
  await expect(exports.getByRole("button", { name: "Approve final exports", exact: true })).toBeDisabled();
  await exports.getByRole("button", { name: "Remove unapproved preview", exact: true }).click();
  await expect(exports.getByText("No PDF has been rendered for this saved revision.")).toBeVisible();
  expect(await (await request.get(url + `/renders?revision_id=${run.revision.id}`)).json()).toEqual([]);
  await expect(page.getByLabel("Resume draft preview")).toContainText("Python prototype");
});

test("incompatible recovered drafts stay downloadable and never reach rendering", async ({ page, request }, info) => {
  const { job, url } = await prepare(request);
  const view = await (await request.get(url)).json();
  const key = `job-pilot:draft:resume-edit-${view.profile_id}-${view.baseline_id}`;
  const raw = '{"old_format":true,"text":"Keep my unsaved accomplishment"}';
  await page.goto(`/jobs/${job.id}`);
  await page.evaluate(({ key, raw }) => { localStorage.setItem(key, raw); sessionStorage.setItem(key, raw); }, { key, raw });
  await page.reload();
  const panel = page.getByRole("region", { name: "Resume review and editing" });
  await expect(panel.getByText(/A recovered edit uses an incompatible/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Render saved revision", exact: true })).toBeDisabled();
  expect(await page.evaluate(key => sessionStorage.getItem(key), key)).toBe(raw);
  const event = page.waitForEvent("download");
  await panel.getByRole("button", { name: "Download recovered edit", exact: true }).click();
  const download = await event;
  const filename = info.outputPath("recovered-draft.json"); await download.saveAs(filename);
  expect(await readFile(filename, "utf8")).toBe(raw);
  await panel.getByRole("button", { name: "Discard incompatible edit", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Render saved revision", exact: true })).toBeEnabled();
  expect(await page.evaluate(key => localStorage.getItem(key), key)).toBeNull();
});

test("recovered description edits block generation until saved or discarded", async ({ page, request }) => {
  const { job } = await prepare(request);
  await page.goto(`/jobs/${job.id}`);
  const key = `job-pilot:draft:tailoring-description-${job.id}`;
  await page.evaluate(key => { localStorage.setItem(key, JSON.stringify({ legacy_text: "Preserve this description" })); }, key);
  await page.reload();
  const panel = page.getByRole("region", { name: "Resume tailoring", exact: true });
  await expect(panel.getByRole("link", { name: "Download job description recovery" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Edit full description" })).toBeDisabled();
  await panel.getByLabel("I reviewed this complete saved job description.").check();
  await expect(panel.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeDisabled();
  await panel.getByRole("button", { name: "Discard incompatible job description" }).click();
  await panel.getByRole("button", { name: "Edit full description" }).click();
  await panel.getByLabel("Full job description for tailoring").fill("An unsaved, changed description");
  await page.reload();
  await panel.getByLabel("I reviewed this complete saved job description.").check();
  await expect(panel.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeDisabled();
  await panel.getByRole("button", { name: "Resume description edit" }).click();
  await expect(panel.getByLabel("Full job description for tailoring")).toHaveValue("An unsaved, changed description");
  await panel.getByRole("button", { name: "Cancel description edit" }).click();
  await expect(panel.getByRole("button", { name: "Generate tailored resume", exact: true })).toBeEnabled();
  expect((await (await request.get(`${backend}/api/jobs/${job.id}`)).json()).source_content).toBe(job.source_content);
});
