// UC-04: the works list.
import { expect, test } from "@playwright/test";
import { columnNames, dataRows, openPage, tableWithColumn } from "./site";

test("UC-04 works page shows Title, Author, Words, Genre, Flags", async ({ page }) => {
  await openPage(page, "/works");
  await expect(page.getByRole("heading", { name: "Works", level: 1 })).toBeVisible();
  const table = tableWithColumn(page, "Flags");
  const expected = ["Title", "Author", "Words", "Genre", "Flags"];
  expect(await columnNames(table)).toEqual(expect.arrayContaining(expected));
  await expect(dataRows(table).first()).toBeVisible();
});
