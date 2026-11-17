// UC-14: crawlers get a real robots.txt and a full sitemap.
import { expect, test } from "@playwright/test";

test("UC-14 robots.txt is plain text, allows all, names the sitemap", async ({ request }) => {
  const response = await request.get("/robots.txt");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("text/plain");
  const body = await response.text();
  expect(body).toMatch(/^User-agent: \*$/m);
  expect(body).not.toMatch(/^Disallow: \/\S*$/m);
  expect(body).toMatch(/^Sitemap: https:\/\/gufime\.com\/sitemap\.xml$/m);
});

test("UC-14 sitemap.xml lists hubs and work and author pages", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("xml");
  const body = await response.text();
  expect(body).toContain('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">');
  for (const hub of ["/", "/works/", "/authors/"]) {
    expect(body).toContain(`<loc>https://gufime.com${hub}</loc>`);
  }
  const workCount = body.match(/<loc>https:\/\/gufime\.com\/works\/[^<]+<\/loc>/g)?.length ?? 0;
  const authorCount = body.match(/<loc>https:\/\/gufime\.com\/authors\/[^<]+<\/loc>/g)?.length ?? 0;
  expect(workCount, "work pages listed").toBeGreaterThan(1000);
  expect(authorCount, "author pages listed").toBeGreaterThan(500);
});
