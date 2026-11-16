// UC-06: filter works by juvenile, play, poetry, or translation flags.
import { expect, test, type Page } from "@playwright/test";
import { columnValues, openPage, tableWithColumn } from "./site";

// Flag groups appear in this order above the works table.
const flagOrder = ["Juvenile", "Play", "Poetry", "Translation"];

/** The "Yes" button of one flag group, by group position. */
function yesButton(page: Page, flag: string) {
  return page.getByRole("button", { name: /^Yes [\d,]+$/ }).nth(flagOrder.indexOf(flag));
}

for (const flag of ["Translation", "Poetry"]) {
  test(`UC-06 choosing ${flag} yes shows only ${flag} works`, async ({ page }) => {
    await openPage(page, "/works");
    await expect(page.getByText(flag, { exact: true }).first()).toBeVisible();
    await yesButton(page, flag).click();
    await expect(async () => {
      const flags = await columnValues(tableWithColumn(page, "Flags"), "Flags");
      expect(flags.length).toBeGreaterThan(0);
      expect(flags.filter((value) => !value.includes(flag))).toEqual([]);
    }).toPass();
  });
}
