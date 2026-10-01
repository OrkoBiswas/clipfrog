import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

test("interactive caption library, logo layout and short render use persisted settings", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Editor Creator");
  await page
    .getByLabel("Email address")
    .fill(`editor-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-long-password-123");
  await page.getByRole("button", { name: "Create your account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Your workspace" }),
  ).toBeVisible();
  const api = "http://localhost:8000/api/v1";
  const headers = { Origin: "http://localhost:3000" };
  const kit = await page.request.post(`${api}/brand-kits`, {
    headers,
    data: { name: "Editor logo" },
  });
  expect(kit.ok(), await kit.text()).toBeTruthy();
  const kitId = (await kit.json()).id;
  expect(
    (
      await page.request.put(`${api}/brand-kits/${kitId}/logo`, {
        headers: { ...headers, "Content-Type": "image/png" },
        data: fs.readFileSync(path.resolve("../../.local/brand-logo.png")),
      })
    ).ok(),
  ).toBeTruthy();
  const response = await page.request.post(`${api}/projects`, {
    headers,
    data: {
      name: "Editor acceptance",
      processing_config: { brand_kit_id: kitId },
    },
  });
  const project = await response.json();
  const base = `${api}/projects/${project.id}`;
  const file = fs.readFileSync(path.resolve("../../.local/fixture.mp4"));
  const upload = await (
    await page.request.post(`${base}/upload/initiate`, {
      headers,
      data: {
        filename: "fixture.mp4",
        size_bytes: file.length,
        mime_type: "video/mp4",
      },
    })
  ).json();
  for (let n = 1; n <= upload.part_count; n++) {
    const signed = await (
      await page.request.post(`${base}/upload/${upload.id}/parts/${n}`, {
        headers,
      })
    ).json();
    expect(
      (
        await page.request.put(signed.url, {
          data: file.subarray((n - 1) * upload.part_size, n * upload.part_size),
        })
      ).ok(),
    ).toBeTruthy();
  }
  await page.request.post(`${base}/upload/${upload.id}/complete`, { headers });
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/jobs`)).json())[0].status,
      { timeout: 60000 },
    )
    .toBe("SUCCEEDED");
  const created = await page.request.post(`${base}/clips`, {
    headers,
    data: {
      title: "Styled clip",
      start_ms: 0,
      end_ms: 4000,
      caption_config: {
        cues: [
          {
            start_ms: 0,
            end_ms: 4000,
            text: "This changes everything about editing",
          },
        ],
      },
    },
  });
  expect(created.ok()).toBeTruthy();
  const clip = await created.json();
  await page.goto(`/projects/${project.id}`);
  await page.getByRole("tab", { name: "Clips", exact: true }).click();
  await page.getByRole("button", { name: "Edit clip", exact: true }).click();
  const editorDialog = page.getByRole("dialog", { name: "Clip editor", exact: true });
  await expect(editorDialog).toBeVisible();
  for (const width of [375, 430, 768, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await editorDialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1), `Editor overflow at ${width}px`).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator(".composition-stage video")).toBeVisible();
  await page.screenshot({ path: "../../.local/redesign-editor-desktop.png" });
  await expect(
    page.getByRole("button", { name: "Apply Creator Impact", exact: true }),
  ).toBeVisible();
  expect(
    await page.getByRole("button", { name: /^Apply / }).count(),
  ).toBeGreaterThanOrEqual(25);
  await page
    .getByRole("button", { name: "Apply Creator Impact", exact: true })
    .click();
  await page.getByRole("button", { name: "Style", exact: true }).click();
  await page.getByRole("button", { name: "Colors", exact: true }).click();
  await page.getByLabel("Text color", { exact: true }).fill("#ff9922");
  await page.getByRole("button", { name: "Style", exact: true }).click();
  await page.getByLabel("Font size", { exact: true }).fill("72");
  await page.getByRole("button", { name: "Animation", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Caption animation", exact: true })
    .selectOption("pop");
  await page.getByRole("button", { name: "Brand", exact: true }).click();
  await page
    .getByRole("button", { name: "Logo placement: top center", exact: true })
    .click();
  await page.getByLabel("Logo opacity", { exact: true }).fill("0.6");
  await page.getByLabel("Logo size", { exact: true }).fill("0.2");
  await page.getByRole("button", { name: "Captions", exact: true }).click();
  await page
    .getByText("My templates: save, rename, duplicate or set default", {
      exact: true,
    })
    .click();
  await page.getByLabel("Custom template name").fill("My amber style");
  await page
    .getByRole("button", { name: "Save as My Template", exact: true })
    .click();
  await expect(page.getByText("Template saved to your library.")).toBeVisible();
  await page
    .getByRole("button", { name: "Render 4-second preview", exact: true })
    .click();
  await expect(page.getByLabel("Rendered style preview")).toBeVisible({
    timeout: 60000,
  });
  const previewUrl = await page
    .getByLabel("Rendered style preview")
    .getAttribute("src");
  const previewBytes = await (await page.request.get(previewUrl!)).body();
  await page
    .locator(".composition-editor")
    .screenshot({ path: "../../.local/editor-preview-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../../.local/redesign-editor-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .locator(".composition-editor")
    .screenshot({ path: "../../.local/editor-preview-mobile.png" });
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "PUT" &&
        response.url().endsWith(`/clips/${clip.id}`),
    ),
    page.getByRole("button", { name: "Save edits", exact: true }).click(),
  ]);
  const saved = (await (await page.request.get(`${base}/clips`)).json()).find(
    (item: { id: string }) => item.id === clip.id,
  );
  expect(saved.caption_config.primary_color).toBe("#ff9922");
  expect(saved.caption_config.animation).toBe("pop");
  expect(saved.overlay_config.logo_position).toBe("top-center");
  expect(saved.overlay_config.logo_opacity).toBe(0.6);
  expect((await (await page.request.get(`${base}/clips`)).json()).length).toBe(
    1,
  );
  const render = await page.request.post(`${base}/clips/${clip.id}/render`, {
    headers,
  });
  expect(render.ok()).toBeTruthy();
  const renderJob = (await render.json()).job_id;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/jobs`)).json()).find(
          (job: { id: string }) => job.id === renderJob,
        ).status,
      { timeout: 60000 },
    )
    .toBe("SUCCEEDED");
  const finalMedia = await (
    await page.request.get(`${base}/clips/${clip.id}/media`)
  ).json();
  const finalBytes = await (await page.request.get(finalMedia.url)).body();
  expect(createHash("sha256").update(finalBytes).digest("hex")).toBe(
    createHash("sha256").update(previewBytes).digest("hex"),
  );
});
