import { expect, test } from "@playwright/test";

/**
 * The ceded-reinsurance desk, end to end through the UI — no AI.
 *
 * Signs in as the seeded demo user (`just seed-demo`) and checks that the
 * intelligence-system surfaces render on real data: the attention queue and its
 * categories, the recoverables portfolio, treaty versions, and the recovery
 * workspace rail. Skipped if the demo desk is not seeded.
 */

const DEMO_EMAIL = "founder@demo-specialty.example";
const DEMO_PASSWORD = "cedeon-demo-password";

async function signIn(page: import("@playwright/test").Page): Promise<boolean> {
  await page.goto("/login");
  await page.getByLabel(/work email/i).fill(DEMO_EMAIL);
  await page.getByLabel(/password/i).fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  try {
    await page.waitForURL(/\/dashboard/, { timeout: 8000 });
    return true;
  } catch {
    return false;
  }
}

test.describe("the demo desk", () => {
  test("Home shows the attention queue and portfolio figures", async ({ page }) => {
    test.skip(!(await signIn(page)), "demo desk not seeded — run `just seed-demo`");

    await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /needs you/i })).toBeVisible();
    await expect(page.getByText(/at a glance/i)).toBeVisible();
    await expect(page.getByText(/open recoverable/i)).toBeVisible();

    // the seed leaves one recoverable overdue → at least one attention item,
    // and it links into a recovery workspace
    const firstItem = page.locator('a[href^="/recovery-candidates/"]').first();
    await expect(firstItem).toBeVisible();
  });

  test("the recoverables portfolio renders the legs and the aging chart", async ({ page }) => {
    test.skip(!(await signIn(page)), "demo desk not seeded");

    await page.goto("/recoverables");
    await expect(page.getByRole("heading", { name: /recoverables/i })).toBeVisible();
    await expect(page.getByText(/aging of what's outstanding/i)).toBeVisible();
    await expect(
      page.getByRole("cell", { name: /Reinsurer (Alpha|Beta|Gamma)/ }).first(),
    ).toBeVisible();
  });

  test("a treaty shows its version history and executable layer", async ({ page }) => {
    test.skip(!(await signIn(page)), "demo desk not seeded");

    await page.goto("/treaties");
    await expect(page.getByRole("heading", { name: "Treaties", level: 1 })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();

    // a treaty that has an executable layer is one that reached Validated / Active —
    // don't depend on the demo treaty's name, which varies with seed vintage
    const executable = page
      .locator("tbody tr")
      .filter({ has: page.getByText(/^(Validated|Active)$/) })
      .first();
    test.skip((await executable.count()) === 0, "no validated treaty in the demo desk");

    await executable.getByRole("link").first().click();
    await expect(page).toHaveURL(/\/treaties\/[0-9a-f-]{36}/);
    await expect(page.getByRole("heading", { name: /^Versions$/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /^Layers?( \(\d+\))?$/ })).toBeVisible();
    await expect(page.getByText("xs", { exact: true }).first()).toBeVisible();
  });

  test("the recovery workspace has its full pipeline rail", async ({ page }) => {
    test.skip(!(await signIn(page)), "demo desk not seeded");

    await page.goto("/recovery-candidates");
    await page.getByRole("link", { name: /^Open/ }).first().click();
    await expect(page).toHaveURL(/\/recovery-candidates\/[0-9a-f-]{36}/);
    for (const label of [
      "Loss basis",
      "Calculation",
      "Investigation",
      "Packet",
      "Notice",
      "Collection",
    ]) {
      await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
  });
});
