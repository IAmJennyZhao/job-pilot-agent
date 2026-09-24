import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "desktop", use: { viewport: { width: 1440, height: 1000 } } }, { name: "mobile", use: { viewport: { width: 390, height: 844 } } }],
  webServer: [
    { command: process.platform === "win32" ? "py -3.13 tests/ux_fixture.py" : "python tests/ux_fixture.py", cwd: "../backend", url: "http://127.0.0.1:8100/health", reuseExistingServer: false, timeout: 60000, env: { UI_FIXTURE_PORT: "8100" } },
    { command: "npm run dev -- --hostname 127.0.0.1 --port 3100", url: "http://127.0.0.1:3100", reuseExistingServer: false, timeout: 120000, env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8100" } }
  ]
});
