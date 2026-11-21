// Shared black-box helpers: page loading, tables, dropdowns, navigation, charts.
import { expect, type Locator, type Page } from "@playwright/test";

/** Open a path and wait until client-side data has loaded. */
export async function openPage(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await waitForData(page);
}

/** Wait until no "Loading..." placeholder remains on the page. */
export async function waitForData(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.getByText("Loading...")).toHaveCount(0);
  await page.waitForLoadState("networkidle");
}

/** The table whose header row includes the given column. */
export function tableWithColumn(page: Page, column: string): Locator {
  const header = page.getByRole("columnheader", { name: column, exact: true });
  return page.getByRole("table").filter({ has: header });
}

/** Data rows only: rows that contain cells, not header cells. */
export function dataRows(table: Locator): Locator {
  return table.getByRole("row").filter({ has: table.page().getByRole("cell") });
}

/** Header names of a table, in order, from its named header row. */
export async function columnNames(table: Locator): Promise<string[]> {
  await expect(table).toBeVisible();
  const headers = table.getByRole("columnheader");
  const names = await headers.allInnerTexts();
  return names.map((name) => name.trim()).filter((name) => name !== "");
}

/** Visible text of one column across every data row. */
export async function columnValues(table: Locator, column: string): Promise<string[]> {
  const position = (await columnNames(table)).indexOf(column);
  expect(position, `column ${column} exists`).toBeGreaterThanOrEqual(0);
  // allInnerTexts never waits, so re-rendered rows cannot hang the test.
  const rows = await dataRows(table).all();
  const cells = await Promise.all(rows.map((row) => row.getByRole("cell").allInnerTexts()));
  return cells.filter((row) => row.length > position).map((row) => row[position].trim());
}

/** Parse a displayed number such as "198,376" or "28.8". */
export function displayedNumber(text: string): number {
  const value = Number(text.replace(/,/g, ""));
  if (Number.isNaN(value)) {
    throw new Error(`Not a displayed number: "${text}"`);
  }
  return value;
}

/** Choose an option from a labelled dropdown, searching by its text. */
export async function pickOption(page: Page, dropdown: string, option: string): Promise<void> {
  await page.getByRole("combobox", { name: dropdown, exact: true }).click();
  const search = page.getByRole("application").getByRole("combobox").filter({ visible: true });
  await search.fill(option);
  await page.getByRole("option", { name: option, exact: true }).filter({ visible: true }).click();
  // The list stays open after choosing, so close it.
  await page.keyboard.press("Escape");
  await expect(search).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: dropdown, exact: true })).toContainText(option);
}

/** Click a link in the site navigation. */
export async function clickNavigation(page: Page, name: string): Promise<void> {
  const navigation = page.getByRole("navigation", { name: "Site" });
  await navigation.getByRole("link", { name, exact: true }).click();
}

/** A chart must be an accessible image named like its heading. */
export async function expectChart(page: Page, heading: RegExp): Promise<void> {
  await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  await expect(page.getByRole("img", { name: heading })).toBeVisible();
}
