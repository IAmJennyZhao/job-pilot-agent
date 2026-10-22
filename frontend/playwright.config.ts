import { defineConfig } from "@playwright/test";

const frontendPort = process.env.UI_FRONTEND_PORT ?? "3100";
if (!/^\d+$/.test(frontendPort) || Number(frontendPort) < 1024 || Number(frontendPort) > 65535) throw new Error("Invalid UI_FRONTEND_PORT");
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: { baseURL: frontendUrl, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "desktop", use: { viewport: { width: 1440, height: 1000 } } }, { name: "mobile", use: { viewport: { width: 390, height: 844 } } }],
  webServer: [
    { command: process.platform === "win32" ? "py -3.13 tests/ux_fixture.py" : "python tests/ux_fixture.py", cwd: "../backend", url: "http://127.0.0.1:8100/health", reuseExistingServer: false, timeout: 60000, env: { UI_FIXTURE_PORT: "8100", UI_FRONTEND_PORT: frontendPort } },
    { command: `npm run dev -- --hostname 127.0.0.1 --port ${frontendPort}`, url: frontendUrl, reuseExistingServer: false, timeout: 120000, env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8100" } }
  ]
});
