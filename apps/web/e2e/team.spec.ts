import { expect, test } from "@playwright/test";

/**
 * The team flow: an admin invites a teammate by email, and the teammate accepts
 * the link to join the same organization as a member. Requires the full stack
 * (`just up`) with `CEDEON_EMAIL_SENDER=console`, so the accept link is surfaced
 * in the UI instead of mailed.
 */
test("an admin invites a teammate who accepts and joins as a member", async ({ page }) => {
  const stamp = Date.now();
  const orgName = `Carrier ${stamp}`;
  const adminEmail = `admin+${stamp}@carrier.example`;
  const teammateEmail = `analyst+${stamp}@carrier.example`;
  const password = "correct-horse-battery-staple";

  // --- the admin registers -------------------------------------------------
  await page.goto("/register");
  await page.getByLabel("Organization").fill(orgName);
  await page.getByLabel("Your name").fill("Head of Ceded Reinsurance");
  await page.getByLabel("Work email").fill(adminEmail);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create workspace/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // --- the admin invites a teammate --------------------------------------
  await page.goto("/settings/members");
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();
  await page.getByLabel("Work email").fill(teammateEmail);
  await page.getByLabel("Role", { exact: true }).selectOption("member");
  await page.getByRole("button", { name: /send invitation/i }).click();

  // Console email sender → the accept link is shown in the UI.
  const devLink = page
    .locator("p", { hasText: "share this link directly" })
    .locator("span.font-mono");
  await expect(devLink).toBeVisible();
  const acceptUrl = (await devLink.textContent())?.trim() ?? "";
  expect(acceptUrl).toContain("/invite/");

  // The pending invitation is listed.
  await expect(page.getByText(teammateEmail)).toBeVisible();

  // --- the admin signs out ---------------------------------------------
  await page.getByRole("button", { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // --- the teammate accepts -------------------------------------------
  await page.goto(acceptUrl);
  const joinButton = page.getByRole("button", { name: new RegExp(`join ${orgName}`, "i") });
  await expect(joinButton).toBeVisible();
  await expect(page.getByText(teammateEmail)).toBeVisible();
  await page.getByLabel("Your name").fill("Reinsurance Analyst");
  await page.getByLabel("Password").fill(password);
  await joinButton.click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("banner").getByText(teammateEmail)).toBeVisible();

  // --- the teammate is a member, not an admin -------------------------
  await page.goto("/settings/members");
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();
  await expect(page.getByText("Invite a teammate")).toHaveCount(0);
  // Both people show in the roster.
  const roster = page.getByRole("rowgroup");
  await expect(roster.getByText(adminEmail)).toBeVisible();
  await expect(roster.getByText(teammateEmail)).toBeVisible();
});

test("an expired-looking or unknown invitation token is rejected", async ({ page }) => {
  await page.goto("/invite/not-a-real-token");
  await expect(page.getByText(/not valid/i)).toBeVisible();
});
