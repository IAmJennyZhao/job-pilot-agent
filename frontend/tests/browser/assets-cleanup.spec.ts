import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { captureWorkspace, captureWorkspaceArea } from "./review-capture";

const backend = "http://127.0.0.1:8100";

test.afterEach(async ({ page }) => {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
});

test("PDF import, extracted edits, manual Ready and merge preserve the original file", async ({ page, request }, info) => {
  const command = "import pymupdf,base64;d=pymupdf.open();p=d.new_page();p.insert_text((72,72),'Synthetic resume original Python accomplishment');print(base64.b64encode(d.tobytes()).decode())";
  const pdf = Buffer.from(execFileSync(process.platform === "win32" ? "py" : "python", [...(process.platform === "win32" ? ["-3.13"] : []), "-c", command], { encoding: "utf8" }).trim(), "base64");
  const profile = await (await request.get(`${backend}/api/profile`)).json();
  const sources = await (await request.get(`${backend}/api/profile/tailoring-sources`)).json();
  await page.goto("/profile?tab=resumes");
  const library = page.getByRole("region", { name: "Reusable resumes", exact: true });
  await library.getByLabel("Resume PDF", { exact: true }).setInputFiles({ name: "original-resume.pdf", mimeType: "application/pdf", buffer: pdf });
  const importedResponse = page.waitForResponse(r => r.request().method() === "POST" && r.url().endsWith("/resume-options/import"));
  await library.getByRole("button", { name: "Import PDF", exact: true }).click();
  const imported = await (await importedResponse).json();
  expect(imported.status).toBe("draft");
  const editor = library.getByRole("region", { name: "Resume editor: original-resume", exact: true });
  await expect(editor).toBeVisible();
  await expect(editor).toContainText("do not modify the originally uploaded PDF");
  await editor.getByRole("textbox", { name: "Skills (one per line)", exact: true }).fill("Python\nUnique merge skill");
  await editor.getByRole("button", { name: "Advanced details", exact: true }).click();
  await editor.getByRole("textbox", { name: "Parsed resume text", exact: true }).fill("Corrected extracted text, separate from the original PDF.");
  await editor.getByRole("button", { name: "Close editor", exact: true }).click();
  const card = library.locator(`[data-asset-id="${imported.id}"]`);
  await expect(card).toContainText("Unsaved draft available");
  await card.getByText("Library actions", { exact: true }).click();
  await expect(card.getByRole("button", { name: "Mark ready", exact: true })).toBeDisabled();
  await card.getByRole("button", { name: "Edit", exact: true }).click();
  await expect(editor.getByRole("textbox", { name: "Parsed resume text", exact: true })).toHaveValue("Corrected extracted text, separate from the original PDF.");
  await editor.getByRole("button", { name: "Save resume variant", exact: true }).click();
  await expect(editor.getByText("Saved successfully.", { exact: true })).toBeVisible();
  let saved = (await (await request.get(`${backend}/api/profile/resume-options`)).json()).find((r: { id: string }) => r.id === imported.id);
  expect(saved.status).toBe("draft");
  expect(saved.parsed_text).toBe("Corrected extracted text, separate from the original PDF.");
  expect(await (await request.get(`${backend}/api/profile`)).json()).toEqual(profile);
  await editor.getByRole("button", { name: "Save & mark ready", exact: true }).click();
  await expect(editor.getByRole("combobox", { name: "Library status" })).toHaveValue("ready");
  expect(await (await request.get(`${backend}/api/profile`)).json()).toEqual(profile);
  await editor.getByText("Merge and library actions", { exact: true }).click();
  await editor.getByRole("button", { name: "Save, mark ready & merge into Base profile", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${backend}/api/profile`)).json()).skills).toContain("Unique merge skill");
  const merged = await (await request.get(`${backend}/api/profile`)).json();
  expect(merged.name).toBe(profile.name);
  expect(merged.resume_text).toBe(profile.resume_text);
  expect(await (await request.get(`${backend}/api/profile/tailoring-sources`)).json()).toEqual(sources);
  const download = page.waitForEvent("download");
  await editor.getByRole("link", { name: "Download original PDF", exact: true }).click();
  const file = info.outputPath("original-after-merge.pdf");
  await (await download).saveAs(file);
  expect(await readFile(file)).toEqual(pdf);
  await page.reload();
  saved = (await (await request.get(`${backend}/api/profile/resume-options`)).json()).find((r: { id: string }) => r.id === imported.id);
  expect(saved.status).toBe("ready");
  expect(await (await request.get(`${backend}/api/profile/resume-options/${imported.id}/download`)).body()).toEqual(pdf);
  await captureWorkspace(page, info, "assets-resume-editor.png");
});

test("closing and switching reusable editors preserves local drafts and disclosures", async ({ page, request }, info) => {
  const stamp = Date.now();
  const one = await (await request.post(`${backend}/api/profile/cover-letter-templates`, { data: { title: `Template one ${stamp}`, body: "Original reusable style" } })).json();
  const two = await (await request.post(`${backend}/api/profile/cover-letter-templates`, { data: { title: `Template two ${stamp}`, body: "Other reusable style" } })).json();
  await page.goto("/profile?tab=templates");
  const library = page.getByRole("region", { name: "Reusable cover letters", exact: true });
  const card = (title: string) => library.locator("section").filter({ has: page.getByRole("heading", { name: title, exact: true }) }).filter({ has: page.getByRole("button", { name: "Edit", exact: true }) });
  await card(one.title).getByRole("button", { name: "Edit", exact: true }).click();
  const editor = library.getByRole("region", { name: `Letter template editor: ${one.title}`, exact: true });
  await editor.getByRole("textbox", { name: "Body", exact: true }).fill("Local reusable prose pending save.");
  await editor.getByRole("button", { name: "Advanced details", exact: true }).click();
  await editor.getByRole("textbox", { name: "Notes", exact: true }).fill("Keep disclosure open");
  await editor.getByRole("button", { name: "Close editor", exact: true }).click();
  await expect(card(one.title)).toContainText("Unsaved template edits available");
  await card(two.title).getByRole("button", { name: "Edit", exact: true }).click();
  await card(one.title).getByRole("button", { name: "Edit", exact: true }).click();
  await expect(editor.getByRole("textbox", { name: "Body", exact: true })).toHaveValue("Local reusable prose pending save.");
  await expect(editor.getByRole("textbox", { name: "Notes", exact: true })).toHaveValue("Keep disclosure open");
  await page.getByRole("navigation", { name: "Application asset views" }).getByRole("button", { name: "Base profile", exact: true }).click();
  await page.goBack();
  await expect(editor.getByRole("textbox", { name: "Notes", exact: true })).toHaveValue("Keep disclosure open");
  await page.reload();
  await card(one.title).getByRole("button", { name: "Edit", exact: true }).click();
  await expect(editor.getByRole("textbox", { name: "Body", exact: true })).toHaveValue("Local reusable prose pending save.");
  await editor.getByRole("button", { name: "Save template", exact: true }).click();
  await expect(editor.getByText("Saved successfully.", { exact: true })).toBeVisible();
  expect((await (await request.get(`${backend}/api/profile/cover-letter-templates`)).json()).find((r: { id: string }) => r.id === one.id).body).toBe("Local reusable prose pending save.");
  await captureWorkspace(page, info, "assets-letter-editor.png");
  await editor.getByRole("button", { name: "Close editor", exact: true }).click();
  await expect(card(one.title)).not.toContainText("Unsaved template edits available");
  await captureWorkspace(page, info, "assets-letter-library.png");
});

test("coverage keeps API results and affected-job links across local navigation", async ({ page, request }, info) => {
  const job = await (await request.post(`${backend}/api/jobs`, { data: { company: `Coverage ${Date.now()}`, role_title: "Rare compliance specialist", category: "Other", required_skills: ["UncommonFramework"], status: "Saved" } })).json();
  await page.goto("/profile?tab=coverage");
  const audit = page.getByRole("region", { name: "Coverage audit", exact: true });
  await audit.getByText("How coverage is calculated", { exact: true }).click();
  await expect(audit).toContainText("last 30 days");
  await expect(audit).toContainText("below 45");
  let writes = 0;
  page.on("request", r => { if (r.method() === "POST" && r.url().endsWith("/coverage-gaps")) writes++; });
  const response = page.waitForResponse(r => r.request().method() === "POST" && r.url().endsWith("/coverage-gaps"));
  await audit.getByRole("button", { name: "Generate audit", exact: true }).click();
  const result = await (await response).json();
  expect(result.gaps.some((g: { affected_job_ids: string[] }) => g.affected_job_ids.includes(job.id))).toBeTruthy();
  for (const gap of result.gaps) await expect(audit.getByRole("heading", { name: gap.title, exact: true })).toBeVisible();
  await audit.locator("summary").filter({ hasText: "Affected jobs" }).first().click();
  const link = audit.getByRole("link").filter({ hasText: job.company }).first();
  // The new job's category might not be first; reveal all returned categories.
  for (const disclosure of await audit.locator("details").filter({ has: page.locator("summary", { hasText: "Affected jobs" }) }).all()) {
    if (await disclosure.getAttribute("open") === null) await disclosure.locator("summary").click();
  }
  await expect(link).toHaveAttribute("href", `/jobs/${job.id}?tab=overview#application-assets`);
  await page.getByRole("navigation", { name: "Application asset views" }).getByRole("button", { name: "Resumes", exact: true }).click();
  await page.goBack();
  await expect(link).toBeVisible();
  expect(writes).toBe(1);
  await captureWorkspace(page, info, "assets-coverage.png");
  await link.click();
  await expect(page.locator("#application-assets")).toBeFocused();
});

test("keyword and explicit AI ranking never select assets automatically", async ({ page, request }, info) => {
  for (let n = 0; n < 4; n++) {
    expect((await request.post(`${backend}/api/profile/resume-options`, { data: { title: `Ranking resume ${Date.now()} ${n}`, status: "ready", skills: ["Python", "FastAPI"], parsed_text: "Python API developer" } })).ok()).toBeTruthy();
  }
  const job = await (await request.post(`${backend}/api/jobs`, { data: { company: `Ranking ${Date.now()}`, role_title: "Backend Engineer", source_content: "Python FastAPI APIs", status: "Saved" } })).json();
  await page.goto(`/jobs/${job.id}?tab=overview#application-assets`);
  const assets = page.getByRole("region", { name: "Reusable asset selection", exact: true });
  await expect(assets.getByLabel("Selected resume", { exact: true })).toHaveValue("");
  const initialResponse = page.waitForResponse(r => r.url().includes("/run-job-intelligence/") && r.request().method() === "POST");
  await assets.getByRole("button", { name: "Initial review", exact: true }).click();
  const initial = await (await initialResponse).json();
  expect(initial.asset_recommendation.source).toBe("keyword");
  await expect(assets.getByLabel("Selected resume", { exact: true })).toHaveValue("");
  const resumes = assets.getByRole("region", { name: "Resume ranking", exact: true });
  await resumes.getByRole("button", { name: /Show all/ }).click();
  await expect(resumes.locator("button[aria-pressed]")).toHaveCount(initial.asset_recommendation.resume_rankings.length);
  const rankingResponse = page.waitForResponse(r => r.url().includes("/rank-assets/") && r.request().method() === "POST");
  await assets.getByRole("button", { name: "AI rank", exact: true }).click();
  const ranked = await (await rankingResponse).json();
  expect(ranked.source).toBe("ai");
  const unchanged = await (await request.get(`${backend}/api/jobs/${job.id}`)).json();
  expect(unchanged.selected_resume_option_id).toBeNull();
  expect(unchanged.selected_cover_letter_template_id).toBeNull();
  await expect(assets.getByLabel("Selected cover letter", { exact: true })).toHaveValue("");
  await captureWorkspaceArea(page, info, "assets-ranking.png", assets);
  const suggestion = resumes.locator("button[aria-pressed]").first();
  await suggestion.click();
  await expect(suggestion).toHaveAttribute("aria-pressed", "true");
  const selected = await assets.getByLabel("Selected resume", { exact: true }).inputValue();
  expect(selected).not.toBe("");
  await page.reload();
  await expect(assets.getByLabel("Selected resume", { exact: true })).toHaveValue(selected);
});
