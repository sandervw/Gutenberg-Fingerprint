// UC-08: the searchable authors list.
import { expect, test } from "@playwright/test";
import { columnNames, dataRows, openPage, tableWithColumn } from "./site";

test("UC-08 authors page shows a searchable Author, Works, Words table", async ({ page }) => {
  await openPage(page, "/authors");
  await expect(page.getByRole("heading", { name: "Authors", level: 1 })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Search" })).toBeVisible();
  const table = tableWithColumn(page, "Author");
  expect(await columnNames(table)).toEqual(expect.arrayContaining(["Author", "Works", "Words"]));
  await expect(dataRows(table).first()).toBeVisible();
});
