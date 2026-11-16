// UC-11: site navigation reaches Home, Works, and Authors from any page.
import { expect, test } from "@playwright/test";
import { clickNavigation, openPage } from "./site";

const destinations = [
  { link: "Works", heading: "Works" },
  { link: "Authors", heading: "Authors" },
  { link: "Home", heading: "Gutenberg Fiction Metrics" },
];

const startPages = ["/", "/works/10662", "/authors/Bond, Nelson S."];

for (const start of startPages) {
  for (const destination of destinations) {
    test(`UC-11 from ${start} the navigation reaches ${destination.link}`, async ({ page }) => {
      await openPage(page, start);
      await clickNavigation(page, destination.link);
      const heading = page.getByRole("heading", { name: destination.heading, level: 1, exact: true });
      await expect(heading).toBeVisible();
    });
  }
}
