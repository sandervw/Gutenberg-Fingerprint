// UC-09: search the authors list by part of a name.
import { expect, test } from "@playwright/test";
import { columnValues, openPage, tableWithColumn } from "./site";

test("UC-09 typing part of a name shows only matching authors", async ({ page }) => {
  await openPage(page, "/authors");
  await page.getByRole("textbox", { name: "Search" }).fill("Leiber");
  await expect(async () => {
    const authors = await columnValues(tableWithColumn(page, "Author"), "Author");
    expect(authors).toContain("Leiber, Fritz");
    expect(authors.filter((name) => !name.includes("Leiber"))).toEqual([]);
  }).toPass();
});
