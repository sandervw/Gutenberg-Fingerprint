// UC-10: an author's page, reached by clicking them in the authors list.
import { expect, test, type Page } from "@playwright/test";
import { expectChart, openPage, tableWithColumn, waitForData } from "./site";

const sampleAuthor = "Bond, Nelson S.";

/** Search the authors list and click the sample author. */
async function openSampleAuthor(page: Page): Promise<void> {
  await openPage(page, "/authors");
  await page.getByRole("textbox", { name: "Search" }).fill("Bond, Nelson");
  const table = tableWithColumn(page, "Author");
  await table.getByRole("cell", { name: sampleAuthor, exact: true }).click();
  await expect(page).toHaveURL(/\/authors\/.+/);
  await waitForData(page);
}

test("UC-10 author page shows name, totals, and section headings", async ({ page }) => {
  await openSampleAuthor(page);
  await expect(page.getByRole("heading", { name: sampleAuthor, level: 1 })).toBeVisible();
  await expect(page.getByText("Works in corpus", { exact: true })).toBeVisible();
  await expect(page.getByText("Total words", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Signature Stylometrics/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Sentence Breakdown/ })).toBeVisible();
});

test("UC-10 Definitions opens to list each metric", async ({ page }) => {
  await openSampleAuthor(page);
  const definitions = page.getByRole("button", { name: /Definitions/ });
  await definitions.click();
  await expect(definitions).toHaveAttribute("aria-expanded", "true");
  const table = tableWithColumn(page, "Metric");
  await expect(table.getByRole("cell", { name: "Mean sentence length", exact: true })).toBeVisible();
  await expect(table.getByRole("cell", { name: "Yule's K", exact: true })).toBeVisible();
});

test("UC-10 author charts are perceivable", async ({ page }) => {
  test.fail(true, "Known site bug: charts have no accessible name.");
  await openSampleAuthor(page);
  await expectChart(page, /^Signature Stylometrics/);
  await expectChart(page, /^Sentence Breakdown/);
});
