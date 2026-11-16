// UC-12: an unknown address shows Page Not Found and a way home.
import { expect, test } from "@playwright/test";

test("UC-12 unknown address shows Page Not Found and a home link", async ({ page }) => {
  await page.goto("/no-such-page-for-uc-12");
  await expect(page.getByRole("heading", { name: "Page Not Found" })).toBeVisible();
  const homeLink = page.getByRole("main").getByRole("link", { name: "Home", exact: true });
  await homeLink.click();
  await expect(page.getByRole("heading", { name: "Gutenberg Fiction Metrics", level: 1 })).toBeVisible();
});
