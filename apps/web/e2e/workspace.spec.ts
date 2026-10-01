import { test, expect } from "@playwright/test";
test("register, create, edit and delete a project", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/login/);
  await page.getByRole("link", { name: "Create an account" }).click();
  await page.getByLabel("Your name").fill("Test Creator");
  await page.getByLabel("Email address").fill(`e2e-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-long-password-123");
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(
    page.getByRole("heading", { name: "Your workspace" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "New Project", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Set up first, upload later" })
    .click();
  await page.getByLabel("Project name").fill("An actual project");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await page.getByRole("link", { name: "Open project", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "An actual project" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "An actual project" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Edit project settings" }).click();
  await page.getByLabel("Project name").fill("Renamed project");
  await page.getByRole("button", { name: /STEP 5 Review/ }).click();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("heading", { name: "Renamed project" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delete project", exact: true })
    .click();
  await page.getByRole("button", { name: "Permanently delete" }).click();
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible();
});
