import { test, expect } from "@playwright/test";
import path from "node:path";

test("workspace routes, themes, responsive layouts and keyboard navigation", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const registration = await page.request.post(
    "http://localhost:8000/api/v1/auth/register",
    {
      headers: { Origin: "http://localhost:3000" },
      data: {
        name: "Alex Morgan",
        email: `design-qa-${Date.now()}@example.com`,
        password: "test-long-password-123",
      },
    },
  );
  expect(registration.ok(), await registration.text()).toBeTruthy();
  let projectId = "";
  for (const [name, type] of [
    ["The creative process · Episode 12", "Podcast"],
    ["Building a better morning routine", "Tutorial"],
    ["Conversations with makers", "Interview"],
  ]) {
    const result = await page.request.post(
      "http://localhost:8000/api/v1/projects",
      {
        headers: { Origin: "http://localhost:3000" },
        data: { name, content_type: type },
      },
    );
    expect(result.ok(), await result.text()).toBeTruthy();
    projectId = (await result.json()).id;
  }
  await page
    .context()
    .storageState({ path: path.resolve("../../.local/redesign-browser.json") });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Your workspace" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.resolve("../../.local/redesign-dashboard-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Expand sidebar" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search workspace" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Search projects and pages" })
    .fill("tmplt");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/templates$/);
  await expect(
    page.getByRole("button", { name: "Apply Creator Impact" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Search workspace", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("dialog", { name: "Search workspace" }),
  ).not.toBeVisible();
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Appearance" }).click();
  await page.getByRole("button", { name: "Light", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const routes = [
    "/dashboard",
    "/projects",
    "/projects/new",
    `/projects/${projectId}`,
    "/clips",
    "/templates",
    "/brand-kit",
    "/usage",
    "/billing",
    "/settings",
  ];
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((value) => {
      localStorage.setItem("clipforge-theme", value);
      window.dispatchEvent(new Event("clipforge-theme"));
    }, theme);
    for (const route of routes) {
      await page.goto(route);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await expect(page.getByText("We couldn’t load this page")).toHaveCount(0);
      for (const width of [375, 430, 768, 1024, 1280, 1440, 1920]) {
        await page.setViewportSize({ width, height: 960 });
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          `${route}, ${theme}, ${width}px overflow`,
        ).toBe(true);
      }
      if (theme === "light" && route === "/dashboard")
        await page.screenshot({
          path: path.resolve("../../.local/redesign-dashboard-light.png"),
          fullPage: true,
        });
    }
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/dashboard");
  await page.screenshot({
    path: path.resolve("../../.local/redesign-dashboard-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  const drawer = page.getByRole("dialog", { name: "ClipForge", exact: true });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("link", { name: "Templates", exact: true }).click();
  await expect(page).toHaveURL(/\/templates$/);
  await expect(drawer).not.toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/projects/new");
  await page.screenshot({
    path: path.resolve("../../.local/redesign-wizard-mobile.png"),
    fullPage: true,
  });
  await expect(page.locator(".page-transition")).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: /^Notifications/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Notifications" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  expect(errors).toEqual([]);
});

test("all authentication screens remain responsive", async ({ page }) => {
  for (const route of [
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/verify-email",
  ]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    for (const width of [375, 430, 768, 1024, 1280, 1440, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `${route} at ${width}px`,
      ).toBe(true);
    }
  }
});
