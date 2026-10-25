import { defineConfig, devices } from "@playwright/test";

/**
 * Browser end-to-end tests against a running stack (normally the Docker
 * Compose one: `make test-e2e` starts it). E2E_BASE_URL overrides the
 * frontend address; the backend address is whatever that frontend was built
 * with.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
