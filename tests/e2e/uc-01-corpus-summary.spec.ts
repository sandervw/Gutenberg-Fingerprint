// UC-01: the home page summarises the corpus.
import { expect, test } from "@playwright/test";
import { openPage } from "./site";

test("UC-01 home shows title, z-score note, work count, and latest date", async ({ page }) => {
  await openPage(page, "/");
  await expect(page.getByRole("heading", { name: "Gutenberg Fiction Metrics", level: 1 })).toBeVisible();
  await expect(page.getByText(/Measured as\s+z-scores/)).toBeVisible();
  const summary = page.getByText(/There are currently\s+[\d,]+\s+works in this corpus/);
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(/arrived on\s+[A-Z][a-z]+ \d{1,2}, \d{4}/);
});
