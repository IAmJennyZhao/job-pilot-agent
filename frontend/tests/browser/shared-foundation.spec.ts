import { expect, test } from "@playwright/test";

test("shared page frame and asset tabs work at desktop and mobile widths", async ({ page }, testInfo) => {
  await page.goto("/profile?tab=base");

  const main = page.locator("#main-content");
  const content = main.locator(":scope > div");
  await expect(page.getByRole("heading", { name: "Application Assets", exact: true })).toBeVisible();
  await expect(content).toBeVisible();
  expect((await content.boundingBox())!.width).toBeLessThanOrEqual(1408);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);

  if (testInfo.project.name === "mobile") {
    await expect(page.locator("header").first()).toBeVisible();
    await expect(page.locator("aside").first()).toBeHidden();
  } else {
    await expect(page.locator("aside").first()).toBeVisible();
  }

  const tabs = page.getByRole("navigation", { name: "Application asset views" });
  await expect(tabs.getByRole("button", { name: "Base profile" })).toHaveAttribute("aria-pressed", "true");
  await tabs.getByRole("button", { name: "Resumes", exact: true }).click();
  await expect(page).toHaveURL(/tab=resumes/);
  await expect(tabs.getByRole("button", { name: "Resumes", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(tabs.getByRole("button", { name: "Resumes", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
});

test("keyboard users can see the skip link focus state", async ({ page }) => {
  await page.goto("/dashboard");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  expect(await skip.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe("solid");
});

test("keyboard navigation opens local views and deferred tools with visible focus", async ({ page }) => {
  await page.goto("/profile?tab=base");
  const nav = page.getByRole("navigation", { name: "Application asset views" });
  const resumes = nav.getByRole("button", { name: "Resumes", exact: true });
  const base = nav.getByRole("button", { name: "Base profile", exact: true });

  await resumes.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/tab=resumes/);
  await expect(resumes).toBeFocused();
  expect(await resumes.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe("solid");
  await expect(page.getByRole("region", { name: "Base profile", exact: true })).toBeHidden();

  await page.keyboard.press("Tab");
  await expect(base).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page).toHaveURL(/tab=base/);
  await expect(page.getByRole("region", { name: "Base profile", exact: true })).toBeVisible();

  const more = nav.locator("summary", { hasText: "More" });
  await more.focus();
  await page.keyboard.press("Enter");
  const coverage = nav.getByRole("link", { name: "Coverage audit" });
  await page.keyboard.press("Tab");
  await expect(coverage).toBeFocused();
  expect(await coverage.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe("solid");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/tab=coverage/);
  await expect(page.getByRole("heading", { name: /Coverage Audit/i }).first()).toBeVisible();
});

test("wide pages keep a centered readable content width", async ({ page }) => {
  await page.setViewportSize({ width: 2200, height: 1000 });
  await page.goto("/dashboard");
  const main = page.locator("#main-content");
  const content = main.locator(":scope > div");
  const mainBox = (await main.boundingBox())!;
  const contentBox = (await content.boundingBox())!;
  expect(contentBox.width).toBeLessThanOrEqual(1408);
  expect(Math.abs(contentBox.x - mainBox.x - (mainBox.width - contentBox.width) / 2)).toBeLessThan(2);
});
