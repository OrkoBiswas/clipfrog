import { expect, test } from "@playwright/test";

test("caption gallery offers built-in styles and customization", async ({ page }) => {
  const registration = await page.request.post(
    "http://localhost:8000/api/v1/auth/register",
    {
      headers: { Origin: "http://localhost:3000" },
      data: {
        name: "Basic Captions",
        email: `basic-captions-${Date.now()}@example.com`,
        password: "test-long-password-123",
      },
    },
  );
  expect(registration.ok()).toBeTruthy();

  await page.goto("/templates");
  await expect(page).toHaveURL(/\/templates$/);
  await expect(
    page.getByRole("link", { name: "Templates", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".ct-card")).toHaveCount(24);
  await page.getByRole("button", { name: "Preview Studio Rise", exact: true }).click();
  await expect(page.getByLabel("Animation", { exact: true })).toHaveValue("word-rise");
});
