import type { Locator, Page, TestInfo } from "@playwright/test";

export async function openAnalytics(page: Page) {
  const summary = page.locator("summary").filter({ hasText: /^Analytics cohort/ });
  if (!await summary.evaluate(element => (element.parentElement as HTMLDetailsElement).open)) await summary.click();
}

/** Capture the actual page from its top, without the development-only Next indicator. */
export async function captureWorkspace(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  await page.screenshot({ path: info.outputPath(name), fullPage: true, style: "nextjs-portal { display: none !important; }" });
}

/** Avoid sticky headers being stitched through a tall panel capture. */
export async function captureWorkspaceArea(page: Page, info: TestInfo, name: string, area: Locator) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  const bounds = await area.boundingBox();
  if (!bounds) throw new Error("Review capture must be visible.");
  await page.screenshot({ path: info.outputPath(name), fullPage: true, clip: bounds, style: "nextjs-portal { display: none !important; }" });
}
