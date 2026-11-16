// Black-box specs against gufime.com, or BASE_URL when set.
import { defineConfig, devices } from "@playwright/test";

const isContinuousIntegration = Boolean(process.env.CI);

/** Desktop and phone projects against BASE_URL, else gufime.com. */
export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: isContinuousIntegration ? 1 : 0,
  workers: 2,
  reporter: isContinuousIntegration ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BASE_URL || "https://gufime.com",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
