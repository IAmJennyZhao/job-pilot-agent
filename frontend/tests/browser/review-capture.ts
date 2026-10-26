import type { Page, TestInfo } from "@playwright/test";

/** Capture the actual page from its top, without the development-only Next indicator. */
export async function captureWorkspace(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  await page.screenshot({ path: info.outputPath(name), fullPage: true, style: "nextjs-portal { display: none !important; }" });
}
