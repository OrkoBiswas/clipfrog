import { test, expect } from "@playwright/test";
import path from "node:path";

test("save a brand kit, upload a logo, apply to a project and retain its saved copy", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Brand Creator");
  await page
    .getByLabel("Email address")
    .fill(`brand-ui-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-long-password-123");
  await page.getByRole("button", { name: "Create your account" }).click();
  await page.getByRole("link", { name: "Brand Kit", exact: true }).click();
  await page.getByLabel("Brand kit name").fill("Studio identity");
  await page
    .getByLabel("Logo image")
    .setInputFiles(path.resolve("../../.local/brand-logo.png"));
  await page.getByRole("button", { name: /2 Caption/ }).click();
  await page
    .getByRole("combobox", { name: "Caption template", exact: true })
    .selectOption("kinetic-bold");
  await page.locator("summary").filter({ hasText: "Color & emphasis" }).click();
  await page.getByLabel("Text color", { exact: true }).fill("#33aaff");

  await page.getByRole("button", { name: "Save brand kit" }).click();
  await expect(
    page.getByText(
      "Brand kit saved. Apply it to a project to use these settings.",
    ),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Edit Studio identity" }).click();
  await page.getByRole("button", { name: /2 Caption/ }).click();
  await page.locator("summary").filter({ hasText: "Color & emphasis" }).click();
  await expect(page.getByLabel("Text color", { exact: true })).toHaveValue("#33aaff");
  await expect(
    page.getByRole("button", { name: "Preview logo" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../.local/brand-kit-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../../.local/brand-kit-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page
    .getByRole("link", { name: "New Project", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Set up first, upload later" })
    .click();
  await page.getByLabel("Project name").fill("Branded project");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await page.getByRole("link", { name: "Open project", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Branded project", exact: true }),
  ).toBeVisible();
  const projectUrl = page.url();
  await page.getByRole("tab", { name: "Brand", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Brand kit", exact: true })
    .selectOption({ label: "Studio identity" });
  await page
    .getByRole("button", { name: "Apply brand kit", exact: true })
    .click();
  await expect(page.getByText(/Applied: Studio identity/)).toBeVisible();
  await page.getByRole("link", { name: "Brand Kit", exact: true }).click();
  await page.getByRole("button", { name: "Delete Studio identity" }).click();
  await page.getByRole("button", { name: "Confirm deletion" }).click();
  await expect(
    page.getByText("No brand kits yet. Create your first one below."),
  ).toBeVisible();
  await page.goto(projectUrl);
  await page.getByRole("tab", { name: "Brand", exact: true }).click();
  await expect(page.getByText(/Applied: Studio identity/)).toBeVisible();
});
