import { expect, test } from "@playwright/test";

/**
 * The core journey through the real frontend, backend and database:
 * sign up → create a board → add a card → it is still there after a reload
 * (so it was persisted, not just rendered) → it shows on the dashboard.
 *
 * Every run uses a fresh email so the test is independent of the data
 * already in the database.
 */
test("sign up, create a board, add a card, see it persist", async ({ page }) => {
  const stamp = Date.now();
  const email = `e2e-${stamp}@example.com`;
  const boardName = `E2E board ${stamp}`;
  const cardTitle = `Write the e2e test ${stamp}`;

  await page.goto("/signup");
  await page.getByLabel("Display name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: /sign up|create account/i }).click();

  await expect(page).toHaveURL(/\/boards$/);
  await expect(page.getByRole("heading", { level: 1, name: "Boards" })).toBeVisible();

  await page.getByLabel("New board name").fill(boardName);
  await page.getByRole("button", { name: "Create board" }).click();
  await page.getByRole("link", { name: boardName }).click();

  await expect(page).toHaveURL(/\/boards\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: boardName })).toBeVisible();
  await expect(page.getByLabel("To Do", { exact: true })).toBeVisible();

  await page.getByLabel("Add card to To Do").fill(cardTitle);
  await page.getByLabel("Add card to To Do").press("Enter");
  await expect(page.getByText(cardTitle)).toBeVisible();

  await page.reload();
  await expect(page.getByText(cardTitle)).toBeVisible();

  await page.getByRole("link", { name: /dashboard/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Total tasks")).toBeVisible();
  await expect(page.getByText("0 of 1 tasks done.")).toBeVisible();
});

test("a wrong password is rejected and the user stays on the login page", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel("Password").fill("definitely wrong");
  await page.getByRole("button", { name: /log in|sign in/i }).click();

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText(/invalid email or password/i)).toBeVisible();
});
