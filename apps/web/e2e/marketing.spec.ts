import { expect, test } from "@playwright/test";

test.describe("the public marketing header", () => {
  test("the theme toggle lives in the header and persists a choice", async ({ page }) => {
    await page.goto("/");
    const header = page.getByRole("banner");

    const dark = header.getByRole("button", { name: "Dark theme" });
    await expect(dark).toBeVisible();
    await dark.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    // The choice survives a reload (persisted to localStorage).
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.getByRole("banner").getByRole("button", { name: "Light theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("a nav link's underline is hidden at rest and drawn on hover", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("banner").getByRole("link", { name: "Security" });

    const scaleX = () =>
      link.evaluate((el) => {
        const t = getComputedStyle(el, "::after").transform;
        // matrix(a, b, c, d, e, f) — "a" is the x-scale; "none" ≈ identity.
        const [, a] = /matrix\(([^,]+)/.exec(t) ?? [];
        return a === undefined ? 1 : Number.parseFloat(a);
      });

    expect(await scaleX()).toBeCloseTo(0, 1);
    await link.hover();
    await expect.poll(scaleX).toBeCloseTo(1, 1);
  });
});
