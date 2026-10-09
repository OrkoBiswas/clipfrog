import { test, expect, type Request } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

test("clip library renders in place and project tabs pause retained media", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const api = "http://localhost:8000/api/v1";
  const headers = { Origin: "http://localhost:3000" };
  const registration = await page.request.post(`${api}/auth/register`, {
    headers,
    data: {
      name: "Library Creator",
      email: `studio-library-${randomUUID()}@example.com`,
      password: "test-long-password-123",
    },
  });
  expect(registration.ok(), await registration.text()).toBeTruthy();
  const projectName = "Library acceptance podcast";
  const response = await page.request.post(`${api}/projects`, {
    headers,
    data: { name: projectName, content_type: "Podcast" },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const project = await response.json();
  const base = `${api}/projects/${project.id}`;
  const file = fs.readFileSync(path.resolve("../../.local/fixture.mp4"));
  const initiated = await page.request.post(`${base}/upload/initiate`, {
    headers,
    data: {
      filename: "fixture.mp4",
      size_bytes: file.length,
      mime_type: "video/mp4",
    },
  });
  expect(initiated.ok(), await initiated.text()).toBeTruthy();
  const upload = await initiated.json();
  for (let number = 1; number <= upload.part_count; number++) {
    const signedResponse = await page.request.post(
      `${base}/upload/${upload.id}/parts/${number}`,
      { headers },
    );
    expect(signedResponse.ok(), await signedResponse.text()).toBeTruthy();
    const signed = await signedResponse.json();
    const part = await page.request.put(signed.url, {
      data: file.subarray(
        (number - 1) * upload.part_size,
        number * upload.part_size,
      ),
    });
    expect(part.ok(), await part.text()).toBeTruthy();
  }
  const completed = await page.request.post(
    `${base}/upload/${upload.id}/complete`,
    { headers },
  );
  expect(completed.ok(), await completed.text()).toBeTruthy();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/jobs`)).json())[0]?.status,
      { timeout: 60_000, message: "Source validation completes" },
    )
    .toBe("SUCCEEDED");
  const created = await page.request.post(`${base}/clips`, {
    headers,
    data: {
      title: "Library moment",
      start_ms: 0,
      end_ms: 4000,
      aspect_ratio: "9:16",
      caption_config: {
        enabled: true,
        cues: [{ start_ms: 0, end_ms: 4000, text: "A moment worth sharing" }],
      },
      render_config: { anchor_x: 0.5, anchor_y: 0.5, quality: "Draft" },
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const clip = await created.json();

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/clips");
  await expect(
    page.getByRole("heading", { name: "Your clips.", exact: true }),
  ).toBeVisible();
  const cards = page.locator(".studio-library-page .studio-clip-card");
  const grid = page.locator(".studio-library-page .studio-clips-grid");
  const search = page.getByRole("textbox", { name: "Search clips" });
  const filter = page.getByRole("combobox", { name: "Filter clips" });
  await expect(cards).toHaveCount(1);
  await search.fill("no-such-moment");
  await expect(
    page.getByRole("heading", { name: "No matching clips" }),
  ).toBeVisible();
  await search.fill(projectName);
  await expect(cards).toHaveCount(1);
  await search.fill("Library moment");
  await expect(cards).toHaveCount(1);
  await search.clear();
  await filter.selectOption("rendered");
  await expect(cards).toHaveCount(0);
  await filter.selectOption("draft");
  await expect(cards).toHaveCount(1);
  await filter.selectOption("all");

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    for (const view of ["List view", "Grid view"]) {
      const toggle = page.getByRole("button", { name: view, exact: true });
      await toggle.click();
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      if (view === "List view") await expect(grid).toHaveClass(/is-list/);
      else await expect(grid).not.toHaveClass(/is-list/);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `Library ${view} fits at ${width}px`,
      ).toBe(true);
      expect(
        await cards
          .first()
          .evaluate(
            (element) => element.scrollWidth <= element.clientWidth + 1,
          ),
        `Clip card ${view} fits at ${width}px`,
      ).toBe(true);
    }
  }

  await cards.getByRole("button", { name: "Edit clip", exact: true }).click();
  const editor = page.getByRole("dialog", { name: "Clip editor", exact: true });
  await expect(editor).toBeVisible();
  await expect(editor.locator(".composition-stage video")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 960 });
    expect(
      await editor.evaluate(
        (element) => element.scrollWidth <= element.clientWidth + 1,
      ),
      `Library editor fits at ${width}px`,
    ).toBe(true);
    const bounds = await editor.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(961);
    await expect(
      editor.getByRole("button", { name: "Save and render", exact: true }),
    ).toBeInViewport();
    if (width === 375)
      await page.screenshot({
        path: path.resolve("../../.local/redesign-library-editor-mobile.png"),
      });
  }
  await page.screenshot({
    path: path.resolve("../../.local/redesign-library-editor.png"),
  });
  await editor
    .getByRole("navigation", { name: "Editor tools" })
    .getByRole("button", { name: "Timing", exact: true })
    .click();
  const editedTitle = "Library moment refined";
  await editor.getByLabel("Clip title", { exact: true }).fill(editedTitle);

  // RSC polling must update this document; the test never reloads the library.
  let documentNavigations = 0;
  const observeNavigation = (request: Request) => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame())
      documentNavigations += 1;
  };
  page.on("request", observeNavigation);
  const [renderResponse] = await Promise.all([
    page.waitForResponse(
      (result) =>
        result.request().method() === "POST" &&
        result.url().endsWith(`/clips/${clip.id}/render`),
    ),
    editor
      .getByRole("button", { name: "Save and render", exact: true })
      .click(),
  ]);
  expect(renderResponse.ok(), await renderResponse.text()).toBeTruthy();
  const renderJob = (await renderResponse.json()).job_id;
  await expect(editor).not.toBeVisible();
  const renderedCard = cards.filter({
    has: page.getByRole("heading", { name: editedTitle, exact: true }),
  });
  await expect(renderedCard).toHaveCount(1);
  const download = renderedCard.getByRole("button", {
    name: `Download ${editedTitle} MP4`,
    exact: true,
  });
  await expect(download).toBeVisible({ timeout: 60_000 });
  await expect(download).toBeEnabled();
  await expect(
    renderedCard.getByRole("button", { name: "Edit clip", exact: true }),
  ).toBeEnabled({ timeout: 10_000 });
  expect(
    documentNavigations,
    "Render completion stays in the same document",
  ).toBe(0);
  page.off("request", observeNavigation);
  const jobs = await (await page.request.get(`${base}/jobs`)).json();
  expect(jobs.find((job: { id: string }) => job.id === renderJob)?.status).toBe(
    "SUCCEEDED",
  );
  await filter.selectOption("draft");
  await expect(cards).toHaveCount(0);
  await filter.selectOption("rendered");
  await expect(cards).toHaveCount(1);
  await filter.selectOption("all");
  await expect(renderedCard.locator("video")).toBeVisible();
  await expect(renderedCard).toHaveCSS("opacity", "1");
  await page.screenshot({
    path: path.resolve("../../.local/redesign-library.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 375, height: 960 });
  await page.screenshot({
    path: path.resolve("../../.local/redesign-library-mobile.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/projects/${project.id}#clips`);
  const clipsTab = page.getByRole("tab", { name: "Clips", exact: true });
  await expect(clipsTab).toHaveAttribute("aria-selected", "true");
  const clipsPanel = page.getByRole("main").locator("#project-panel-clips");
  const video = clipsPanel.locator(".studio-clip-card video");
  await expect(video).toBeVisible();
  const player = await video.elementHandle();
  expect(player).not.toBeNull();
  await video.evaluate(async (element: HTMLVideoElement) => {
    element.muted = true;
    element.loop = true;
    element.currentTime = 0;
    await element.play();
  });
  await expect
    .poll(() => video.evaluate((element: HTMLVideoElement) => element.paused))
    .toBe(false);
  await page.getByRole("tab", { name: "Brand", exact: true }).click();
  await expect(clipsPanel).toBeHidden();
  await expect
    .poll(() => player!.evaluate((element: HTMLVideoElement) => element.paused))
    .toBe(true);
  expect(await player!.evaluate((element) => element.isConnected)).toBe(true);
  await clipsTab.click();
  await expect(video).toBeVisible();
  expect(
    await video.evaluate((element, retained) => element === retained, player!),
    "Switching tabs retains the same preview element",
  ).toBe(true);
  expect(
    await video.evaluate((element: HTMLVideoElement) => element.paused),
  ).toBe(true);
  expect(errors).toEqual([]);
});
