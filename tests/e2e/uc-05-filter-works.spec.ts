// UC-05: filter works by author, genre, and title.
import { expect, test, type Page } from "@playwright/test";
import { columnValues, openPage, pickOption, tableWithColumn } from "./site";

const sampleAuthor = "Morris, William";
const sampleGenre = "Horror";
const sampleTitle = "Udolpho";

/** Wait until every value in a column satisfies the check. */
async function expectColumn(page: Page, column: string, check: (value: string) => boolean) {
  await expect(async () => {
    const values = await columnValues(tableWithColumn(page, "Flags"), column);
    expect(values.length).toBeGreaterThan(0);
    expect(values.filter((value) => !check(value))).toEqual([]);
  }).toPass();
}

/** Flag counts reflect the whole filtered set, so they fingerprint it. */
async function flagCounts(page: Page): Promise<string[]> {
  return page.getByRole("button", { name: /^(Yes|No) [\d,]+$/ }).allInnerTexts();
}

test("UC-05 picking an author shows only that author's works", async ({ page }) => {
  await openPage(page, "/works");
  await pickOption(page, "Author", sampleAuthor);
  await expectColumn(page, "Author", (value) => value === sampleAuthor);
});

test("UC-05 picking a genre shows only that genre", async ({ page }) => {
  await openPage(page, "/works");
  await pickOption(page, "Genre", sampleGenre);
  await expectColumn(page, "Genre", (value) => value === sampleGenre);
});

test("UC-05 typing part of a title shows only matching titles", async ({ page }) => {
  await openPage(page, "/works");
  await page.getByRole("textbox", { name: "Type to search" }).fill(sampleTitle);
  await expectColumn(page, "Title", (value) => value.toLowerCase().includes(sampleTitle.toLowerCase()));
});

test("UC-05 clearing every filter shows every work again", async ({ page }) => {
  await openPage(page, "/works");
  const unfiltered = await flagCounts(page);
  const titleSearch = page.getByRole("textbox", { name: "Type to search" });
  await pickOption(page, "Author", sampleAuthor);
  await pickOption(page, "Genre", "Fantasy");
  await titleSearch.fill("Wood");
  await expect.poll(() => flagCounts(page)).not.toEqual(unfiltered);
  await pickOption(page, "Author", "All authors");
  await pickOption(page, "Genre", "All genres");
  await titleSearch.fill("");
  await expect.poll(() => flagCounts(page)).toEqual(unfiltered);
});
