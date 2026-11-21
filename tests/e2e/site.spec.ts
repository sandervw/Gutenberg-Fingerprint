// One black-box test per use case in docs/use-cases/site.md.
import { expect, test, type Locator, type Page } from "@playwright/test";

const workPage = "/works/10662";
const authorPage = "/authors/Bond, Nelson S.";

/** Open a path and wait for its main heading. */
async function openPage(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
}

/** The table whose header row includes the given column. */
function tableWithColumn(page: Page, column: string): Locator {
  return page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: column, exact: true }) });
}

/** Visible text of one column across every data row. */
async function columnValues(table: Locator, column: string): Promise<string[]> {
  const names = (await table.getByRole("columnheader").allInnerTexts()).map((name) => name.trim());
  expect(names, `no column "${column}"`).toContain(column);
  const position = names.indexOf(column);
  const rows = await table.getByRole("row").filter({ has: table.page().getByRole("cell") }).all();
  const cells = await Promise.all(rows.map((row) => row.getByRole("cell").allInnerTexts()));
  return cells.map((row) => row[position].trim());
}

/** Expect every value in a works-table column to pass the check. */
async function expectWorksColumn(page: Page, column: string, check: (value: string) => boolean): Promise<void> {
  await expect(async () => {
    const values = await columnValues(tableWithColumn(page, "Flags"), column);
    expect(values.length).toBeGreaterThan(0);
    expect(values.filter((value) => !check(value))).toEqual([]);
  }).toPass();
}

/** Choose an option from a labelled dropdown, searching by its text. */
async function pickOption(page: Page, dropdown: string, option: string): Promise<void> {
  await page.getByRole("combobox", { name: dropdown, exact: true }).click();
  await page.getByRole("application").getByRole("combobox").filter({ visible: true }).fill(option);
  await page.getByRole("option", { name: option, exact: true }).filter({ visible: true }).click();
  await page.keyboard.press("Escape");
}

/** WCAG contrast between two "rgb(r, g, b)" colours. */
function contrast(first: string, second: string): number {
  const luminance = (colour: string) => {
    const channels = colour.match(/[\d.]+/g);
    if (channels === null) throw new Error(`unparsed colour ${colour}`);
    const [red, green, blue] = channels.map((value) => {
      const scaled = Number(value) / 255;
      return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const [light, dark] = [luminance(first), luminance(second)].sort((left, right) => right - left);
  return (light + 0.05) / (dark + 0.05);
}

/** The h1 text colour and the nearest painted background behind it. */
function headingColours(page: Page): Promise<string[]> {
  return page.getByRole("heading", { level: 1 }).first().evaluate((heading) => {
    for (let node: Element | null = heading; node !== null; node = node.parentElement) {
      const background = getComputedStyle(node).backgroundColor;
      if (background !== "rgba(0, 0, 0, 0)") return [getComputedStyle(heading).color, background];
    }
    return [getComputedStyle(heading).color, "rgb(255, 255, 255)"];
  });
}

test("UC-01 home summarises the corpus", async ({ page }) => {
  await openPage(page, "/");
  await expect(page.getByRole("heading", { name: "Gutenberg Fiction Metrics", level: 1 })).toBeVisible();
  await expect(page.getByText(/Measured as\s+z-scores/)).toBeVisible();
  await expect(page.getByText(/There are currently\s+[\d,]+\s+works.+arrived on\s+[A-Z][a-z]+ \d{1,2}, \d{4}/s)).toBeVisible();
});

test("UC-02 Weirdest Works lists 25 rows by Excess and opens a work", async ({ page }) => {
  await openPage(page, "/");
  const table = tableWithColumn(page, "Excess");
  for (const column of ["Work", "Author", "Genre", "Words"]) {
    await expect(table.getByRole("columnheader", { name: column, exact: true })).toBeVisible();
  }
  const excess = (await columnValues(table, "Excess")).map(Number);
  expect(excess).toHaveLength(25);
  expect(excess).toEqual([...excess].sort((left, right) => right - left));
  const [title] = await columnValues(table, "Work");
  await table.getByRole("cell", { name: title, exact: true }).click();
  await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();
});

test("UC-03 home shows the Vocabulary Overlap chart", async ({ page }) => {
  await openPage(page, "/");
  const chart = page.getByRole("img", { name: /Vocabulary Overlap/ });
  // Author names read "Surname, Given", so commas mark the bar labels.
  expect(await chart.locator("text").filter({ hasText: "," }).count()).toBeGreaterThan(1);
});

test("UC-04 works page lists Title, Author, Words, Genre, Flags", async ({ page }) => {
  await openPage(page, "/works");
  for (const column of ["Title", "Author", "Words", "Genre", "Flags"]) {
    await expect(page.getByRole("columnheader", { name: column, exact: true })).toBeVisible();
  }
});

test("UC-05 works filter by author, genre, and title, then clear", async ({ page }) => {
  await openPage(page, "/works");
  const unfiltered = await page.getByRole("button", { name: /^(Yes|No) [\d,]+$/ }).allInnerTexts();
  await pickOption(page, "Author", "Morris, William");
  await expectWorksColumn(page, "Author", (value) => value === "Morris, William");
  await pickOption(page, "Genre", "Fantasy");
  await expectWorksColumn(page, "Genre", (value) => value === "Fantasy");
  await page.getByRole("textbox", { name: "Type to search" }).fill("Wood");
  await expectWorksColumn(page, "Title", (value) => value.includes("Wood"));
  await pickOption(page, "Author", "All authors");
  await pickOption(page, "Genre", "All genres");
  await page.getByRole("textbox", { name: "Type to search" }).fill("");
  await expect.poll(() => page.getByRole("button", { name: /^(Yes|No) [\d,]+$/ }).allInnerTexts()).toEqual(unfiltered);
});

test("UC-06 a flag filter narrows the works", async ({ page }) => {
  await openPage(page, "/works");
  // Flag groups run Juvenile, Play, Poetry, Translation; the third is Poetry.
  await page.getByRole("button", { name: /^Yes [\d,]+$/ }).nth(2).click();
  await expectWorksColumn(page, "Flags", (value) => value.includes("Poetry"));
});

test("UC-07 a work page shows its byline and charts", async ({ page }) => {
  await openPage(page, "/works");
  await page.getByRole("textbox", { name: "Type to search" }).fill("The Night Land");
  await tableWithColumn(page, "Flags").getByRole("cell", { name: "The Night Land", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The Night Land", level: 1 })).toBeVisible();
  await expect(page.getByText(/^By .+ - Undetermined novel, [\d,]+ words\.$/)).toBeVisible();
  for (const chart of [/^Departure from the Author's Norm/, /^Work Signature/, /^Sentence Type Mix/]) {
    await expect(page.getByRole("img", { name: chart })).toBeVisible();
  }
  await page.getByRole("link", { name: "Hodgson, William Hope" }).click();
  await expect(page.getByRole("heading", { name: "Hodgson, William Hope", level: 1 })).toBeVisible();
});

test("UC-08 authors page lists Author, Works, Words with search", async ({ page }) => {
  await openPage(page, "/authors");
  await expect(page.getByRole("textbox", { name: "Search" })).toBeVisible();
  for (const column of ["Author", "Works", "Words"]) {
    await expect(page.getByRole("columnheader", { name: column, exact: true })).toBeVisible();
  }
});

test("UC-09 author search shows only matching authors", async ({ page }) => {
  await openPage(page, "/authors");
  await page.getByRole("textbox", { name: "Search" }).fill("Leiber");
  await expect(async () => {
    const authors = await columnValues(tableWithColumn(page, "Author"), "Author");
    expect(authors).toContain("Leiber, Fritz");
    expect(authors.filter((name) => !name.includes("Leiber"))).toEqual([]);
  }).toPass();
});

test("UC-10 an author page shows totals, charts, and definitions", async ({ page }) => {
  await openPage(page, authorPage);
  await expect(page.getByText("Works in corpus", { exact: true })).toBeVisible();
  await expect(page.getByText("Total words", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Signature Stylometrics/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Sentence Breakdown/ })).toBeVisible();
  await page.getByRole("button", { name: /Definitions/ }).click();
  await expect(tableWithColumn(page, "Metric").getByRole("cell", { name: "Yule's K", exact: true })).toBeVisible();
});

test("UC-11 the navigation reaches Works, Authors, and Home", async ({ page }) => {
  await openPage(page, workPage);
  const navigation = page.getByRole("navigation", { name: "Site" });
  for (const [link, heading] of [["Works", "Works"], ["Authors", "Authors"], ["Home", "Gutenberg Fiction Metrics"]]) {
    await navigation.getByRole("link", { name: link, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading, level: 1, exact: true })).toBeVisible();
  }
});

test("UC-12 an unknown address shows Page Not Found and a home link", async ({ page }) => {
  await page.goto("/no-such-page-for-uc-12");
  await expect(page.getByRole("heading", { name: "Page Not Found" })).toBeVisible();
  await page.getByRole("main").getByRole("link", { name: "Home", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Gutenberg Fiction Metrics", level: 1 })).toBeVisible();
});

test("UC-13 phones never scroll sideways and both themes stay readable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/", "/works", workPage]) {
    await openPage(page, path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} scrolls sideways`).toBeLessThanOrEqual(0);
  }
  for (const theme of ["Light", "Dark"]) {
    await page.getByRole("group", { name: "Theme" }).getByRole("button", { name: theme, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme.toLowerCase());
    const [text, background] = await headingColours(page);
    expect(contrast(text, background), `${theme} heading contrast`).toBeGreaterThanOrEqual(4.5);
  }
});

test("UC-14 robots.txt and sitemap.xml serve crawlers", async ({ request }) => {
  const robots = await request.get("/robots.txt");
  expect(robots.headers()["content-type"]).toContain("text/plain");
  const rules = await robots.text();
  expect(rules).toMatch(/^User-agent: \*$/m);
  expect(rules).not.toMatch(/^Disallow: \/\S*$/m);
  expect(rules).toMatch(/^Sitemap: https:\/\/gufime\.com\/sitemap\.xml$/m);
  const sitemap = await (await request.get("/sitemap.xml")).text();
  for (const path of ["/", "/works/", "/authors/"]) {
    expect(sitemap).toContain(`<loc>https://gufime.com${path}</loc>`);
  }
  expect(sitemap.match(/<loc>https:\/\/gufime\.com\/works\/[^<]+<\/loc>/g)?.length ?? 0).toBeGreaterThan(1000);
  expect(sitemap.match(/<loc>https:\/\/gufime\.com\/authors\/[^<]+<\/loc>/g)?.length ?? 0).toBeGreaterThan(500);
});
