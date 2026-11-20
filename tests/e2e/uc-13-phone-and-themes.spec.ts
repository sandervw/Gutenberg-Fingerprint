// UC-13: no sideways scrolling on phones; readable light and dark themes.
import { expect, test, type Page } from "@playwright/test";
import { openPage } from "./site";

const samplePages = ["/", "/works", "/authors", "/works/10662", "/authors/Bond, Nelson S."];

/** Pixels the page can scroll sideways beyond the viewport. */
function sidewaysOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

type Box = { left: number; top: number; right: number; bottom: number };

/** True when two boxes share any area. */
function boxesOverlap(first: Box, second: Box): boolean {
  const apartSideways = first.right <= second.left || second.right <= first.left;
  const apartUpright = first.bottom <= second.top || second.bottom <= first.top;
  return !apartSideways && !apartUpright;
}

/** Pairs of text labels that overlap inside any chart on the page. */
async function overlappingChartLabels(page: Page): Promise<number> {
  const charts = await page.getByRole("img", { name: / chart$/ }).all();
  const chartBoxes = await Promise.all(
    charts.map((chart) =>
      chart.locator("text").evaluateAll((labels) =>
        labels.map((label) => {
          const { left, top, right, bottom } = label.getBoundingClientRect();
          return { left, top, right, bottom };
        }),
      ),
    ),
  );
  const pairs = chartBoxes.flatMap((boxes) =>
    boxes.flatMap((box, position) => boxes.slice(position + 1).filter((other) => boxesOverlap(box, other))),
  );
  return pairs.length;
}

/** Relative luminance of an "rgb(r, g, b)" colour, per WCAG. */
function luminance(colour: string): number {
  const channels = (colour.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
  if (channels.length < 3) {
    throw new Error(`Unparsable colour: "${colour}"`);
  }
  const linear = channels.map((value) => {
    const scaled = value / 255;
    return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/** Luminance of the h1 text and of its nearest painted backdrop. */
async function headingLuminance(page: Page): Promise<{ text: number; backdrop: number }> {
  const [text, backdrop] = await page.getByRole("heading", { level: 1 }).first().evaluate((heading) => {
    const textColour = getComputedStyle(heading).color;
    // Walk up until an ancestor paints a background.
    for (let node: Element | null = heading; node !== null; node = node.parentElement) {
      const background = getComputedStyle(node).backgroundColor;
      if (background !== "rgba(0, 0, 0, 0)") {
        return [textColour, background];
      }
    }
    return [textColour, "rgb(255, 255, 255)"];
  });
  return { text: luminance(text), backdrop: luminance(backdrop) };
}

/** WCAG contrast ratio between two luminances. */
function contrast(first: number, second: number): number {
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

/** Cycle the Appearance menu item until it reads the wanted theme. */
async function chooseTheme(page: Page, theme: "Light" | "Dark"): Promise<void> {
  const appearance = page.getByRole("menuitem", { name: /^Appearance/ });
  // Appearance cycles Light, Dark, System; four checks reach any theme.
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (!(await appearance.isVisible())) {
      // A short timeout fails fast when the button is covered.
      await page.getByRole("button", { name: "Menu" }).click({ timeout: 10_000 });
    }
    if ((await appearance.innerText()).includes(theme)) {
      break;
    }
    await appearance.click();
  }
  await expect(appearance).toContainText(theme);
  await page.keyboard.press("Escape");
}

for (const path of samplePages) {
  test(`UC-13 ${path} has no sideways scrolling at phone width`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone width only");
    await openPage(page, path);
    const overflow = await sidewaysOverflow(page);
    expect(overflow, `${path} scrolls sideways by ${overflow}px`).toBeLessThanOrEqual(0);
  });
}

for (const path of samplePages) {
  test(`UC-13 ${path} chart labels do not overlap at phone width`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone width only");
    await openPage(page, path);
    const overlaps = await overlappingChartLabels(page);
    expect(overlaps, `${path} has ${overlaps} overlapping chart labels`).toBe(0);
  });
}

for (const theme of ["Light", "Dark"] as const) {
  test(`UC-13 ${theme} theme keeps text readable`, async ({ page }) => {
    await openPage(page, "/");
    await chooseTheme(page, theme);
    const shades = await headingLuminance(page);
    expect(contrast(shades.text, shades.backdrop)).toBeGreaterThanOrEqual(4.5);
    // Dark means light text on a dark backdrop, and vice versa.
    expect(shades.backdrop < shades.text).toBe(theme === "Dark");
  });
}
