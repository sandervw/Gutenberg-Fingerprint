// Black-box specs against gufime.com, or BASE_URL when set.
import { defineConfig, devices } from "@playwright/test";

/** One desktop project against BASE_URL, else gufime.com. */
export default defineConfig({
  testDir: ".",
  timeout: 20_000,
  expect: { timeout: 5_000 },
  retries: 0,
  workers: 4,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BASE_URL || "https://gufime.com",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
});
