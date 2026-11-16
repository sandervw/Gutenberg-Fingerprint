// UC-03: the Vocabulary Overlap chart on the home page.
import { expect, test } from "@playwright/test";
import { expectChart, openPage } from "./site";

test("UC-03 home shows the Vocabulary Overlap section", async ({ page }) => {
  await openPage(page, "/");
  await expect(page.getByRole("heading", { name: "Vocabulary Overlap" })).toBeVisible();
  await expect(page.getByText(/Jaccard overlap of vocabulary/)).toBeVisible();
});

test("UC-03 Vocabulary Overlap chart is perceivable", async ({ page }) => {
  test.fail(true, "Known site bug: charts have no accessible name.");
  await openPage(page, "/");
  await expectChart(page, /Vocabulary Overlap/);
});
