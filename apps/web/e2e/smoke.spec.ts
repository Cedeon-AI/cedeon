import { expect, test } from "@playwright/test";

/**
 * Phase 1 happy path. Requires the full stack running (`just up`).
 * Run with: `pnpm test:e2e`
 */
test("a new organization can register and reach the dashboard", async ({ page }) => {
  const stamp = Date.now();
  const email = `owner+${stamp}@carrier.example`;

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /contract to recovery/i })).toBeVisible();

  await page.goto("/register");
  await page.getByLabel("Organization").fill(`Carrier ${stamp}`);
  await page.getByLabel("Your name").fill("VP Ceded Reinsurance");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: /create organization/i }).click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();
  await expect(page.getByRole("banner").getByText(email)).toBeVisible();

  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login/);
});
