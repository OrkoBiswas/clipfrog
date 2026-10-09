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
    page.getByRole("heading", { name: "Welcome back, Alex." }),
  ).toBeVisible();
  await page.screenshot({
    path: path.resolve("../../.local/redesign-dashboard-dark.png"),
    fullPage: true,
  });
  for (const ratio of ["1:1", "16:9", "9:16"]) {
    const option = page
      .getByRole("group", { name: "Preview aspect ratio" })
      .getByRole("button", { name: ratio, exact: true });
    await option.click();
    await expect(option).toHaveAttribute("aria-pressed", "true");
  }
  await page.getByRole("button", { name: "Show sample captions" }).click();
  await expect(page.locator(".showcase-caption")).toHaveCount(0);
  await page.getByRole("button", { name: "Show sample captions" }).click();
  await expect(page.locator(".showcase-caption")).toBeVisible();
  await page.getByRole("button", { name: "Grid view", exact: true }).click();
  for (const width of [375, 768, 1201, 1280, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `Dashboard grid at ${width}px`,
    ).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "List view", exact: true }).click();
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
    .fill("settings");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/settings$/);
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
    "/brand-kit",
    "/usage",
    "/billing",
    "/settings",
  ];
  await page.goto(`/projects/${projectId}#clips`);
  await expect(
    page.getByRole("tab", { name: "Clips", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Brand", exact: true }).click();
  await expect(page).toHaveURL(/#brand$/);
  await page.goBack();
  await expect(
    page.getByRole("tab", { name: "Clips", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: /01 Upload/ }).click();
  await expect(page.locator("#source")).toBeFocused();
  await expect(
    page.getByRole("tab", { name: "Overview", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "Step 1: Upload your video", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze video", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Find highlights", exact: true })).toBeDisabled();
  await expect(page.getByText("Complete video analysis in step 2 to unlock highlight search.")).toBeVisible();
  await page.screenshot({
    path: path.resolve("../../.local/redesign-project.png"),
    fullPage: true,
  });
  await page.goto(`/projects/${projectId}?tab=clips`);
  await expect(
    page.getByRole("tab", { name: "Clips", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
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
  await expect(
    page.getByRole("heading", { name: "Welcome back, Alex." }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator(".creator-hero:visible")).toHaveCSS("opacity", "1");
  await page.screenshot({
    path: path.resolve("../../.local/redesign-dashboard-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  const drawer = page.getByRole("dialog", { name: "ClipForge", exact: true });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Templates", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
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
    if (route === "/login") {
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(() =>
        Promise.all(
          document
            .getAnimations()
            .filter(
              (animation) =>
                animation.effect?.getTiming().iterations !== Infinity,
            )
            .map((animation) => animation.finished),
        ),
      );
      await page.screenshot({
        path: path.resolve("../../.local/redesign-login.png"),
        fullPage: true,
      });
    }
  }
});
