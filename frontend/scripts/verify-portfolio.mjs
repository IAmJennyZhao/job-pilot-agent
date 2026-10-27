import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { chromium } from "@playwright/test";

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const directory = path.resolve(frontend, "../docs/assets/screenshots");
const manifest = JSON.parse(await fs.readFile(path.join(directory, "manifest.json"), "utf8"));
assert.equal(manifest.fictional, true);
assert.equal(manifest.screenshots.length, 10);
for (const shot of manifest.screenshots) {
  for (const format of ["original", "web"]) {
    const file = shot[format];
    const bytes = await fs.readFile(path.join(directory, file.file));
    assert.equal(bytes.length, file.bytes);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), file.sha256);
    assert.ok(file.width > 0 && file.height > 0);
  }
}
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(pathToFileURL(path.join(directory, "index.html")).href);
  assert.equal(await page.locator("article:not([hidden])").count(), 10);
  await page.locator("img").evaluateAll(async images => {
    for (const image of images) image.loading = "eager";
    await Promise.all(images.map(image => image.decode()));
    if (images.some(image => !image.naturalWidth)) throw new Error("Gallery image failed to decode");
  });
  await page.getByRole("button", { name: "Primary", exact: true }).click();
  assert.equal(await page.locator("article:not([hidden])").count(), 2);
  await page.getByRole("button", { name: "Mobile", exact: true }).click();
  assert.equal(await page.locator("article:not([hidden])").count(), 2);
  await page.getByRole("button", { name: "All", exact: true }).click();
  assert.equal(await page.locator("article:not([hidden])").count(), 10);
  await page.screenshot({ path: path.join(frontend, "logs/portfolio-gallery.png"), fullPage: false });
  console.log("Verified 20 image hashes, 10 decoded gallery images, and All/Primary/Mobile filters.");
} finally {
  await browser.close();
}
