import { openAnalytics } from "./review-capture";
import { expect, test } from "@playwright/test";

const backend = "http://127.0.0.1:8100";

test("four primary destinations and backup utility remain reachable", async ({ page }, testInfo) => {
  await page.goto("/dashboard");
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Menu" }).click();
    const drawer = page.getByRole("dialog", { name: "Navigation menu" });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("navigation", { name: "Mobile navigation" }).getByRole("link")).toHaveCount(4);
    await expect(drawer.getByRole("link", { name: "Export & backups" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(page.getByRole("button", { name: "Menu" })).toBeFocused();
  } else {
    const sidebar = page.locator("aside");
    await expect(sidebar.getByRole("navigation", { name: "Primary navigation" }).getByRole("link")).toHaveCount(4);
    await expect(sidebar.getByRole("link", { name: "Export & backups" })).toBeVisible();
  }
});

test("Dashboard views, old report links and filters survive refresh and history", async ({ page }) => {
  await page.goto("/reports?since=2099-01-01&group=category");
  await expect(page).toHaveURL(/\/dashboard\?.*since=2099-01-01.*group=category.*tab=outcomes/);
  await expect(page.getByRole("heading", { name: "Search outcomes" })).toBeVisible();
  await expect(page.getByLabel("Group by", { exact: true })).toHaveValue("category");
  await page.reload();
  await openAnalytics(page);
  await expect(page.getByLabel("Jobs saved on or after (UTC)", { exact: true })).toHaveValue("2099-01-01");

  const tabs = page.getByRole("navigation", { name: "Dashboard views" });
  await tabs.getByRole("button", { name: "Skills & learning" }).click();
  await expect(page).toHaveURL(/tab=skills/);
  await expect(page.getByRole("heading", { name: "Skills & learning", exact: true })).toBeVisible();
  await page.goBack();
  await expect(tabs.getByRole("button", { name: "Outcomes" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Group by", { exact: true })).toHaveValue("category");
  await page.goForward();
  await expect(tabs.getByRole("button", { name: "Skills & learning" })).toHaveAttribute("aria-pressed", "true");
  await page.goto("/skills?focus=python");
  await expect(page).toHaveURL(/\/dashboard\?.*focus=python.*tab=skills/);
  await expect(tabs.locator("summary")).toHaveCount(0);
  await page.goto("/dashboard?focus=python&tab=skills#study-plan");
  await expect(page).toHaveURL(/tab=skills.*#study-plan/);
  await expect(page.locator("#study-plan")).toBeVisible();
});

test("Assets views keep a draft while tabs and browser history change", async ({ page }) => {
  await page.goto("/profile");
  await expect(page.getByRole("navigation", { name: "Application asset views" }).getByRole("button", { name: "Base profile" })).toHaveAttribute("aria-pressed", "true");
  const name = page.getByLabel("Name", { exact: true });
  await name.fill("Navigation draft");
  const tabs = page.getByRole("navigation", { name: "Application asset views" });
  await tabs.getByRole("button", { name: "Resumes", exact: true }).click();
  await expect(page).toHaveURL(/tab=resumes/);
  await page.goBack();
  await expect(name).toHaveValue("Navigation draft");
  await tabs.getByRole("button", { name: "Tailoring sources" }).click();
  await expect(page.getByRole("heading", { name: "Tailoring sources", exact: true })).toBeVisible();
  await page.reload();
  await expect(tabs.getByRole("button", { name: "Tailoring sources" })).toHaveAttribute("aria-pressed", "true");
  await page.goto("/profile?tab=coverage");
  await expect(page.getByRole("heading", { name: /Coverage Audit/i }).first()).toBeVisible();
});

test("Job views and legacy tailoring/status anchors select their owner", async ({ page, request }) => {
  const response = await request.post(`${backend}/api/jobs`, { data: { company: `Navigation ${Date.now()}`, role_title: "Engineer", source_content: "Build reliable APIs.", status: "Saved" } });
  expect(response.ok()).toBeTruthy();
  const job = await response.json();
  await page.goto(`/jobs/${job.id}?tailoring=prepare#tailoring-preparation`);
  const tabs = page.getByRole("navigation", { name: "Job views" });
  await expect(tabs.getByRole("button", { name: "Resume", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("region", { name: "Resume tailoring" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Resume tailoring" })).toBeVisible();
  await tabs.getByRole("button", { name: "Cover letter" }).click();
  await expect(page).toHaveURL(/tab=letter/);
  await expect(page.getByRole("region", { name: "Cover letters" })).toBeVisible();
  await tabs.getByRole("button", { name: "History" }).click();
  await expect(page.getByRole("heading", { name: "Status History" })).toBeVisible();
  await page.goBack();
  await expect(tabs.getByRole("button", { name: "Cover letter" })).toHaveAttribute("aria-pressed", "true");
  await page.goto(`/jobs/${job.id}#status-history`);
  await expect(tabs.getByRole("button", { name: "History" })).toHaveAttribute("aria-pressed", "true");
  await tabs.locator("summary").click();
  await tabs.getByRole("link", { name: "Asset ranking" }).click();
  await expect(tabs.getByRole("button", { name: "Overview" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#application-assets")).toBeVisible();
});

test("Interview Practice and History are direct-entry views", async ({ page }) => {
  await page.goto("/interview?tab=history");
  const tabs = page.getByRole("navigation", { name: "Interview views" });
  await expect(tabs.getByRole("button", { name: "History" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Session History" })).toBeVisible();
  await page.reload();
  await expect(tabs.getByRole("button", { name: "History" })).toHaveAttribute("aria-pressed", "true");
  await tabs.getByRole("button", { name: "Practice" }).click();
  await expect(page).toHaveURL(/tab=practice/);
  await page.goBack();
  await expect(tabs.getByRole("button", { name: "History" })).toHaveAttribute("aria-pressed", "true");
  await tabs.locator("summary").click();
  await tabs.getByRole("link", { name: "Command Center" }).click();
  await expect(tabs.getByRole("button", { name: "History" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#command-center")).toBeVisible();
});
