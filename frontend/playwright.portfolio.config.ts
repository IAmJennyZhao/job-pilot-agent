import { defineConfig } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// Keep capture compilation independent of a normal running Next dev server.
// Only public application sources/config are copied, never .env, data or assets storage.
const frontendRoot = __dirname;
const logs = path.resolve(frontendRoot, "../logs");
fs.mkdirSync(logs, { recursive: true });
const snapshot = fs.mkdtempSync(path.join(logs, "portfolio-app-"));
fs.symlinkSync(path.join(frontendRoot, "node_modules"), path.join(snapshot, "node_modules"), "junction");
for (const name of ["src", "public", "package.json", "tsconfig.json", "next-env.d.ts", "next.config.ts", "tailwind.config.ts", "postcss.config.js"]) {
  const source = path.join(frontendRoot, name);
  if (fs.existsSync(source)) fs.cpSync(source, path.join(snapshot, name), { recursive: true });
}

// Separate from the regression suite and the owner's normal :3000/:8000 app.
export default defineConfig({
  testDir: "./scripts",
  testMatch: "portfolio-capture.spec.ts",
  workers: 1,
  timeout: 180000,
  expect: { timeout: 20000 },
  outputDir: "logs/portfolio-capture",
  use: { baseURL: "http://127.0.0.1:3120", viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 2, timezoneId: "America/New_York", colorScheme: "light" },
  webServer: [
    { command: process.platform === "win32" ? "py -3.13 scripts/portfolio_demo.py" : "python scripts/portfolio_demo.py", cwd: "../backend", url: "http://127.0.0.1:8120/health", reuseExistingServer: false, timeout: 120000 },
    { command: `"${process.execPath}" "${path.join(frontendRoot, "node_modules/next/dist/bin/next")}" dev --hostname 127.0.0.1 --port 3120`, cwd: snapshot, url: "http://127.0.0.1:3120", reuseExistingServer: false, timeout: 120000, env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8120" } }
  ]
});
