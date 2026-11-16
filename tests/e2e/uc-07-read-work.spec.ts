// UC-07: a work's page, reached by clicking it in the works list.
import { expect, test, type Page } from "@playwright/test";
import { expectChart, openPage, tableWithColumn, waitForData } from "./site";

const chartHeadings = [/^Departure from the Author's Norm/, /^Work Signature/, /^Sentence Type Mix/];

/** Search the works list for a title and click its row. */
async function openWorkFromList(page: Page, title: string): Promise<void> {
  await openPage(page, "/works");
  await page.getByRole("textbox", { name: "Type to search" }).fill(title);
  const table = tableWithColumn(page, "Flags");
  await table.getByRole("cell", { name: title, exact: true }).click();
  await expect(page).toHaveURL(/\/works\/[^/]+\/?$/);
  await waitForData(page);
}

/** The "By author - genre type, N words." line under the title. */
function bylineOf(page: Page) {
  return page.getByText(/^By .+ words\.$/);
}

test("UC-07 work page shows title, author, genre, type, words, sections", async ({ page }) => {
  await openWorkFromList(page, "The Mysterious Island");
  await expect(page.getByRole("heading", { name: "The Mysterious Island", exact: true })).toBeVisible();
  const byline = bylineOf(page);
  await expect(byline.getByRole("link", { name: "Verne, Jules" })).toBeVisible();
  await expect(byline).toContainText("Sci-Fi");
  await expect(byline).toContainText("novel");
  await expect(byline).toContainText("193,298");
  for (const heading of chartHeadings) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
});

test("UC-07 author link opens the author's page", async ({ page }) => {
  await openWorkFromList(page, "The Mysterious Island");
  await bylineOf(page).getByRole("link", { name: "Verne, Jules" }).click();
  await expect(page).toHaveURL(/\/authors\//);
  await waitForData(page);
  await expect(page.getByRole("heading", { name: "Verne, Jules" })).toBeVisible();
});

test("UC-07 work page shows the genre when it is Undetermined", async ({ page }) => {
  await openWorkFromList(page, "The Night Land");
  await expect(bylineOf(page)).toContainText("Undetermined");
});

test("UC-07 work charts are perceivable", async ({ page }) => {
  await openWorkFromList(page, "The Mysterious Island");
  for (const heading of chartHeadings) {
    await expectChart(page, heading);
  }
});
