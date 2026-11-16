// UC-02: the Weirdest Works table on the home page.
import { expect, test } from "@playwright/test";
import { columnNames, columnValues, dataRows, displayedNumber, openPage, tableWithColumn } from "./site";

test("UC-02 Weirdest Works lists 25 rows, highest Excess first", async ({ page }) => {
  await openPage(page, "/");
  await expect(page.getByRole("heading", { name: "Weirdest Works" })).toBeVisible();
  const table = tableWithColumn(page, "Excess");
  expect(await columnNames(table)).toEqual(expect.arrayContaining(["Work", "Author", "Genre", "Words", "Excess"]));
  await expect(dataRows(table)).toHaveCount(25);
  const excess = (await columnValues(table, "Excess")).map(displayedNumber);
  const sorted = [...excess].sort((left, right) => right - left);
  expect(excess).toEqual(sorted);
});

test("UC-02 clicking a Weirdest Works row opens that work", async ({ page }) => {
  await openPage(page, "/");
  const table = tableWithColumn(page, "Excess");
  const [title] = await columnValues(table, "Work");
  await table.getByRole("cell", { name: title, exact: true }).click();
  await expect(page).toHaveURL(/\/works\/[^/]+\/?$/);
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
});
