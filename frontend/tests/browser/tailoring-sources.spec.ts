import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("review, activate, reload and revoke fictional tailoring sources", async ({ page }, testInfo) => {
  const command = process.platform === "win32" ? "py" : "python";
  const args = [...(process.platform === "win32" ? ["-3"] : []), "-c",
    "import sys,json;sys.path.insert(0,'tests');from tailoring_fixtures import import_payload;print(json.dumps(import_payload()))"];
  const bundle = JSON.parse(execFileSync(command, args, { cwd: path.resolve(process.cwd(), "../backend"), encoding: "utf8" }));
  bundle.bank_markdown = bundle.bank_markdown.replace("bank_version: synthetic.1", `bank_version: browser.${Date.now()}`);
  let aiCalls = 0;
  page.on("request", request => { if (request.url().includes("/api/ai/")) aiCalls++; });
  await page.goto("/profile?tab=sources");
  const panel = page.getByRole("region", { name: "Tailoring sources" });
  await expect(panel.getByRole("heading", { name: "Tailoring sources" })).toBeVisible();
  await panel.getByText("Import a source bundle", { exact: true }).click();
  for (const [label, key, filename] of [
    ["Experience bank (.md)", "bank_markdown", "bank.md"],
    ["Job preferences (.yaml)", "preferences_yaml", "preferences.yaml"],
    ["Resume layout (.tex)", "template_tex", "layout.tex"],
    ["Layout style guide (.md)", "style_guide", "style.md"]
  ]) {
    await panel.getByLabel(label, { exact: true }).setInputFiles({ name: filename, mimeType: "text/plain", buffer: Buffer.from(bundle[key]) });
  }
  await panel.getByRole("button", { name: "Import and validate" }).click();
  await expect(panel.getByText("Source status: pending", { exact: true })).toBeVisible();
  await expect(panel.getByText("EXCLUDED_CLAIM_SECRET", { exact: false })).toBeVisible();
  const activate = panel.getByRole("button", { name: "Activate reviewed sources" });
  await expect(activate).toBeDisabled();
  await panel.getByLabel("I reviewed this version's facts, exclusions, preferences, and layout sources.").check();
  await activate.click();
  await expect(panel.getByText("Source status: active", { exact: true })).toBeVisible();
  await page.reload();
  await expect(panel.getByText("Source status: active", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await panel.screenshot({ path: testInfo.outputPath("active-sources.png") });
  await panel.getByRole("button", { name: "Revoke this version" }).click();
  await expect(panel.getByText("Source status: revoked", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Activate reviewed sources" })).toHaveCount(0);
  expect(aiCalls).toBe(0);
});
