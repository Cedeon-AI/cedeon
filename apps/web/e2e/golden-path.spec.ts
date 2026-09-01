import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * The full vertical slice, end to end through the UI:
 *   set up a treaty (wizard) → real AI extraction → validate the terms →
 *   start a recovery (wizard) → import claims → deterministic calculation →
 *   the recovery workspace and its section rail.
 *
 * Hits the real Anthropic API, so it is skipped unless CEDEON_LIVE_E2E is set.
 * Requires the full stack (`just up`) with ANTHROPIC_API_KEY configured, and:
 *   CEDEON_LIVE_E2E=1 CEDEON_WEB_PUBLIC_URL=http://localhost:3100 pnpm test:e2e golden-path
 */
test.skip(
  !process.env.CEDEON_LIVE_E2E,
  "set CEDEON_LIVE_E2E=1 to run — this test calls the real Anthropic API",
);

const FIX = path.resolve(here, "../../../packages/fixtures");
const GOLDEN = "$8,700,000.00";

test("treaty → validate → recovery → workspace, with the $8.7M golden figure", async ({ page }) => {
  test.setTimeout(240_000);
  const stamp = Date.now();

  // --- register --------------------------------------------------------------
  await page.goto("/register");
  await page.getByLabel("Organization").fill(`Golden ${stamp}`);
  await page.getByLabel("Your name").fill("Ceded Re Analyst");
  await page.getByLabel("Work email").fill(`golden+${stamp}@carrier.example`);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: /create workspace/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();

  // --- set up a treaty (wizard) -------------------------------------------
  await page.goto("/treaties/new");
  await page.setInputFiles('input[type="file"]', `${FIX}/treaty-2027-property-cat-xol.pdf`);
  await expect(page.getByText(/Parsed — page and clause structure/i)).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: /Continue/i }).click();
  await page
    .getByPlaceholder("Atlantic Specialty Insurance Company")
    .fill("Demo Specialty Insurance Co.");
  await page
    .getByPlaceholder("2027 Property Catastrophe Program")
    .fill("2027 Property Cat Program");
  await page.getByPlaceholder("2027 Property Cat XOL").fill("2027 Property Cat XOL");
  await page.getByRole("button", { name: /Create & extract/i }).click();

  // --- extraction, then validate ----------------------------------------
  const toValidate = page.getByRole("link", { name: /Validate the proposed terms/i });
  await expect(toValidate).toBeVisible({ timeout: 150_000 });
  await toValidate.click();
  await expect(page).toHaveURL(/\/validate/);

  for (const key of ["attachment", "limit"]) {
    await page.getByTestId(`term-confirm-${key}`).click();
    await expect(page.getByTestId(`term-${key}`)).toHaveAttribute("data-resolution", "confirmed");
  }
  const parts = page.getByTestId("participation-row");
  const partCount = await parts.count();
  expect(partCount).toBeGreaterThan(0);
  for (let i = 0; i < partCount; i++) {
    await parts.nth(i).getByTestId("participation-confirm").click();
    await expect(parts.nth(i)).toHaveAttribute("data-resolution", "confirmed");
  }

  await page.getByRole("button", { name: /Validate treaty/i }).click();
  await expect(page.getByText(/This treaty version is already validated/i)).toBeVisible({
    timeout: 15_000,
  });

  // --- start a recovery (wizard) --------------------------------------
  await page.goto("/recovery-candidates/new");
  await expect(page.getByText(/occurrence basis/i)).toBeVisible();
  await page.getByPlaceholder("Hurricane Béatrice 2027").fill(`Hurricane Demo ${stamp}`);
  await page.getByRole("button", { name: /Create & continue/i }).click();

  await page.setInputFiles('input[type="file"]', `${FIX}/hurricane-demo-2027-claims.csv`);
  await page.getByRole("button", { name: /^Validate rows$/i }).click();
  await expect(page.getByText(/10 ok/i)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /Commit .* claim/i }).click();
  await expect(page.locator("#w-rec-treaty")).toBeVisible({ timeout: 15_000 });

  await page.locator("#w-rec-treaty").selectOption({ index: 1 });
  await page.getByRole("button", { name: /Continue/i }).click();
  await page.getByRole("button", { name: /Calculate the recovery/i }).click();

  // --- the recovery workspace --------------------------------------
  await expect(page).toHaveURL(/\/recovery-candidates\/[0-9a-f-]{36}/);
  await expect(page.getByRole("heading", { name: "Recovery" })).toBeVisible();
  await expect(page.getByText(GOLDEN, { exact: true })).toBeVisible({ timeout: 15_000 });
  // the per-reinsurer split
  await expect(page.getByText("$4,350,000.00", { exact: true })).toBeVisible();
  await expect(page.getByText("$2,610,000.00", { exact: true })).toBeVisible();
  await expect(page.getByText("$1,740,000.00", { exact: true })).toBeVisible();

  // rail navigation
  await page.getByRole("link", { name: "Investigation" }).click();
  await expect(page).toHaveURL(/section=investigation/);
  await expect(page.getByText(/AI investigation/i)).toBeVisible();

  await page.getByRole("link", { name: "Packet" }).click();
  await expect(page).toHaveURL(/section=packet/);
  await expect(page.getByRole("heading", { name: /Recovery packet/i })).toBeVisible();

  // the legacy /packet URL still works — it redirects into the workspace
  const base = page.url().split("?")[0];
  await page.goto(`${base}/packet`);
  await expect(page).toHaveURL(/section=packet/);

  // --- confirm the recovery, then track collection ------------------
  await page.goto(`${base}?section=calculation`);
  await page.getByRole("button", { name: /^Confirm$/ }).click();
  await expect(page.getByText(/Confirmed/i).first()).toBeVisible({ timeout: 10_000 });

  await page.getByRole("link", { name: "Collection" }).click();
  await expect(page).toHaveURL(/section=collection/);
  await page.getByRole("button", { name: /Start collection tracking/i }).click();

  // one leg per reinsurer, the golden split, and an "advance" action
  await expect(page.getByText("$4,350,000.00").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("$2,610,000.00").first()).toBeVisible();
  await expect(page.getByText("$1,740,000.00").first()).toBeVisible();
  await page
    .getByRole("row")
    .filter({ hasText: /4,350,000/ })
    .getByRole("button", { name: /Mark notified/i })
    .click();
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: /4,350,000/ })
      .getByText("Notified", { exact: true }),
  ).toBeVisible({ timeout: 10_000 });
});
