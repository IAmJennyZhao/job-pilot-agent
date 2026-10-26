import { captureWorkspace } from "./review-capture";
import { expect, test } from "@playwright/test";

const backend = "http://127.0.0.1:8100";

test("asset editors, file selection and readiness focus survive local navigation", async ({ page, request }, info) => {
  await page.goto("/profile?tab=resumes");
  const tabs = page.getByRole("navigation", { name: "Application asset views" });
  const resumes = page.getByRole("region", { name: "Reusable resumes", exact: true });
  const base = page.getByRole("region", { name: "Base profile", exact: true });
  const letters = page.getByRole("region", { name: "Reusable cover letters", exact: true });
  const originalTitle = await resumes.getByLabel("Title", { exact: true }).inputValue();
  const records = await (await request.get(`${backend}/api/profile/resume-options`)).json();
  const original = records.find((item: { title: string }) => item.title === originalTitle);
  expect(original).toBeTruthy();
  let writes = 0;
  page.on("request", req => { if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method())) writes++; });
  await resumes.getByLabel("Resume PDF", { exact: true }).setInputFiles({ name: "pending-resume.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 pending upload") });
  const draftTitle = `Reusable draft ${Date.now()}`;
  await resumes.getByLabel("Title", { exact: true }).fill(draftTitle);
  await captureWorkspace(page, info, "assets-resumes-page.png");

  await tabs.getByRole("button", { name: "Base profile", exact: true }).click();
  await base.getByLabel("Name", { exact: true }).fill("Avery Morgan — unsaved");
  await base.getByRole("button", { name: "Advanced details", exact: true }).click();
  await base.getByLabel("Raw resume text", { exact: true }).fill("Candidate information kept while switching views.");
  await captureWorkspace(page, info, "assets-profile-page.png");

  await tabs.getByRole("button", { name: "Cover Letters", exact: true }).click();
  await letters.getByRole("button", { name: "Edit", exact: true }).first().click();
  await letters.getByLabel("Body", { exact: true }).fill("Reusable letter draft that has not been saved.");
  await letters.getByRole("button", { name: "Advanced details", exact: true }).click();
  await letters.getByLabel("Notes", { exact: true }).fill("Keep this editor open.");
  await captureWorkspace(page, info, "assets-letters-page.png");

  await tabs.getByRole("button", { name: "Tailoring sources", exact: true }).click();
  await page.goBack();
  await expect(letters.getByLabel("Body", { exact: true })).toHaveValue("Reusable letter draft that has not been saved.");
  await expect(letters.getByLabel("Notes", { exact: true })).toHaveValue("Keep this editor open.");
  await tabs.getByRole("button", { name: "Resumes", exact: true }).click();
  await expect(resumes.getByLabel("Title", { exact: true })).toHaveValue(draftTitle);
  await expect(resumes.getByLabel("Resume PDF", { exact: true })).toHaveValue(/pending-resume\.pdf$/);
  await expect(base).toBeHidden();
  await expect(letters).toBeHidden();
  await page.getByRole("button", { name: "Skills", exact: true }).click();
  await expect(base.getByLabel("Skills (one per line)", { exact: true })).toBeFocused();
  await expect(base.getByLabel("Name", { exact: true })).toHaveValue("Avery Morgan — unsaved");
  await expect(base.getByLabel("Raw resume text", { exact: true })).toHaveValue("Candidate information kept while switching views.");
  expect(writes).toBe(0);
  expect(await (await request.get(`${backend}/api/profile/resume-options`)).json()).toEqual(records);

  await tabs.getByRole("button", { name: "Resumes", exact: true }).click();
  await resumes.getByRole("button", { name: "Save resume variant", exact: true }).click();
  await expect(resumes.getByText("Saved successfully.", { exact: true })).toBeVisible();
  const updated = await (await request.get(`${backend}/api/profile/resume-options`)).json();
  expect(updated.find((item: { id: string }) => item.id === original.id).title).toBe(draftTitle);
  expect(writes).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
});
