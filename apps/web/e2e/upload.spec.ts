import { test, expect } from "@playwright/test";
import path from "node:path";

test("upload a real video directly to MinIO and validate through Celery", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Video Creator");
  await page
    .getByLabel("Email address")
    .fill(`upload-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-long-password-123");
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(
    page.getByRole("heading", { name: /^Welcome back,/ }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "New Project", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Set up first, upload later" })
    .click();
  await page.getByLabel("Project name").fill("Real upload check");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await page.getByRole("link", { name: "Open project", exact: true }).click();
  await page
    .getByLabel("Choose source video")
    .setInputFiles(path.resolve("../../.local/fixture.mp4"));
  await page.getByRole("button", { name: "Upload video", exact: true }).click();
  await expect(page.getByText("Upload complete", { exact: true })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText(/640 × 360/)).toBeVisible();
  await page.reload();
  await expect(page.getByText("uploaded", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Clips", exact: true }).click();
  await page
    .getByRole("button", { name: "Create manual clip", exact: true })
    .click();
  await page.getByRole("button", { name: "Timing", exact: true }).click();
  await page
    .getByLabel("Clip title", { exact: true })
    .fill("Browser rendered clip");
  await page.getByLabel("Start (seconds)", { exact: true }).fill("0.5");
  await page.getByLabel("End (seconds)", { exact: true }).fill("3.5");
  await page.getByRole("button", { name: "Text", exact: true }).click();
  await page.getByLabel("Opening title overlay").fill("Real rendered video");
  await page
    .getByRole("button", { name: "Save and render", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Preview Browser rendered clip",
      exact: true,
    }),
  ).toBeVisible({ timeout: 60_000 });
  await page
    .getByRole("button", { name: "Preview Browser rendered clip", exact: true })
    .click();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect
    .poll(() =>
      video.evaluate((element: HTMLVideoElement) => element.readyState),
    )
    .toBeGreaterThanOrEqual(2);
  expect(
    await video.evaluate((element: HTMLVideoElement) => element.videoWidth),
  ).toBe(1080);
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", {
      name: "Download Browser rendered clip MP4",
      exact: true,
    })
    .click();
  expect((await download).suggestedFilename()).toMatch(/\.mp4$/);
});
