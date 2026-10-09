import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

test("font variants and automatic collage toggle preview, persist, and render together", async ({ page }) => {
  test.setTimeout(180_000);
  page.setDefaultTimeout(15_000);
  const api = "http://localhost:8000/api/v1";
  const headers = { Origin: "http://localhost:3000" };
  let projectId = "";
  try {
    const registration = await page.request.post(`${api}/auth/register`, {
      headers, data: { name: "Split Screen", email: `split-${Date.now()}@example.com`, password: "test-long-password-123" },
    });
    expect(registration.ok(), await registration.text()).toBeTruthy();
    const createdProject = await page.request.post(`${api}/projects`, { headers, data: { name: "Split screen verification" } });
    expect(createdProject.ok(), await createdProject.text()).toBeTruthy();
    projectId = (await createdProject.json()).id;
    const base = `${api}/projects/${projectId}`;
    const file = fs.readFileSync(path.resolve("../../.local/fixture.mp4"));
    const upload = await (await page.request.post(`${base}/upload/initiate`, {
      headers, data: { filename: "fixture.mp4", size_bytes: file.length, mime_type: "video/mp4" },
    })).json();
    for (let part = 1; part <= upload.part_count; part++) {
      const signed = await (await page.request.post(`${base}/upload/${upload.id}/parts/${part}`, { headers })).json();
      const result = await page.request.put(signed.url, { data: file.subarray((part - 1) * upload.part_size, part * upload.part_size) });
      expect(result.ok(), await result.text()).toBeTruthy();
    }
    expect((await page.request.post(`${base}/upload/${upload.id}/complete`, { headers })).ok()).toBeTruthy();
    await expect.poll(async () => (await (await page.request.get(`${base}/jobs`)).json())[0].status, { timeout: 60_000 }).toBe("SUCCEEDED");
    // Known detector output isolates composition behavior from model accuracy.
    // This belongs only to the disposable project created above.
    execFileSync("docker", ["compose", "exec", "-T", "api", "python", "-c", `
import uuid
from clipforge_api.db import SessionLocal
from clipforge_api.models import Analysis, Scene, Transcript
with SessionLocal() as db:
    project_id = uuid.UUID('${projectId}')
    db.add(Analysis(project_id=project_id, face_frames=[{'detector': 'yunet-collage-v1', 'timestamp': i / 3, 'faces': [{'confidence': 0.95, 'x': x - 0.04, 'y': 0.24, 'w': 0.08, 'h': 0.22, 'center_x': x, 'center_y': 0.35} for x in ([0.5] if i < 6 else [0.25, 0.5, 0.75])]} for i in range(12)]))
    db.add(Scene(project_id=project_id, start_ms=0, end_ms=2000))
    db.add(Scene(project_id=project_id, start_ms=2000, end_ms=4000))
    db.add(Transcript(project_id=project_id, language='en', full_text='Medium black and wide captions', segments=[{'start': 0, 'end': 4, 'text': 'Medium black and wide captions', 'words': [{'start': 0.1, 'end': 0.4, 'text': 'Medium'}, {'start': 0.4, 'end': 0.8, 'text': 'black'}, {'start': 2, 'end': 2.4, 'text': 'and'}, {'start': 2.4, 'end': 2.8, 'text': 'wide'}, {'start': 2.8, 'end': 3.5, 'text': 'captions'}]}]))
    db.commit()
`], { cwd: path.resolve("../.."), timeout: 30_000 });
    // Project settings are the user's entry point; verify the actual settings
    // surface before testing template and per-clip overrides below.
    await page.goto(`/projects/${projectId}#settings`);
    const settings = page.getByRole("tabpanel", { name: "Settings", exact: true });
    await expect(settings).toBeVisible();
    await settings.getByRole("button", { name: "Edit project settings", exact: true }).click();
    const setup = settings.getByRole("navigation", { name: "Project setup progress" });
    await setup.getByRole("button", { name: /Captions & brand/ }).click();
    const projectLayout = settings.locator("details").filter({
      has: page.locator("summary").filter({ hasText: "Layout & safe area" }),
    });
    if ((await projectLayout.getAttribute("open")) === null)
      await projectLayout.locator("summary").click();
    await projectLayout.getByRole("switch", { name: "Multiple screens", exact: true }).check();
    await expect(projectLayout.getByRole("switch", { name: "Multiple screens", exact: true })).toBeChecked();
    await expect(projectLayout.getByRole("button", { name: "Side by side", exact: true })).toHaveCount(0);
    await expect(projectLayout.getByRole("combobox", { name: "Panel 2 person", exact: true })).toHaveCount(0);
    await projectLayout.screenshot({ path: "../../.local/project-split-screen-settings.png" });
    await setup.getByRole("button", { name: /Review/ }).click();
    await expect(settings.getByRole("heading", { name: "Everything look right?", exact: true })).toBeVisible();
    const projectSave = page.waitForResponse((response) =>
      response.request().method() === "PUT" && response.url().endsWith(`/projects/${projectId}`),
    );
    await settings.getByRole("button", { name: "Save changes", exact: true }).click();
    const savedProjectResponse = await projectSave;
    expect(savedProjectResponse.ok(), await savedProjectResponse.text()).toBeTruthy();
    const projectSettings = await (await page.request.get(base)).json();
    expect(projectSettings.processing_config.render_config.layout).toBe("auto");
    expect(projectSettings.processing_config.render_config.panels).toHaveLength(0);
    const createdClip = await page.request.post(`${base}/clips`, {
      headers, data: {
        title: "Three voices", start_ms: 0, end_ms: 4000,
        caption_config: { cues: [{ start_ms: 0, end_ms: 4000, text: "Medium black and wide captions" }] },
      },
    });
    expect(createdClip.ok(), await createdClip.text()).toBeTruthy();
    const clip = await createdClip.json();
    // Omitting render_config must inherit the saved project layout for a manual clip.
    expect(clip.render_config.layout).toBe("auto");
    expect(clip.render_config.panels).toEqual(projectSettings.processing_config.render_config.panels);
    await page.goto("/templates");
    await page.getByRole("button", { name: "Preview Studio Rise", exact: true }).click();
    const templateEditor = page.getByRole("dialog", { name: "Customize Studio Rise", exact: true });
    await templateEditor.locator("summary").filter({ hasText: "Layout & safe area" }).click();
    await templateEditor.getByRole("switch", { name: "Multiple screens", exact: true }).check();
    await templateEditor.getByLabel("Project", { exact: true }).selectOption(projectId);
    await templateEditor.getByRole("checkbox", { name: /Three voices/ }).check();
    await templateEditor.getByRole("button", { name: "Apply to 1 clip", exact: true }).click();
    await expect(templateEditor.getByRole("region", { name: "Apply caption template" }).getByRole("status")).toContainText("Style saved to 1 clip");
    const styled = (await (await page.request.get(`${base}/clips`)).json()).find((item: { id: string }) => item.id === clip.id);
    expect(styled.render_config.layout).toBe("auto");
    expect(styled.caption_config.cues[0].text).toBe("Medium black and wide captions");
    await templateEditor.getByRole("link", { name: "Open clips", exact: true }).click();
    await page.getByRole("button", { name: "Edit clip", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Clip editor", exact: true });
    const inspector = dialog.locator(".studio-inspector");
    const rail = dialog.getByRole("navigation", { name: "Editor tools" });
    await inspector.getByLabel("Font family", { exact: true }).selectOption("Urbanist");
    await inspector.getByLabel("Font weight", { exact: true }).selectOption("500");
    await expect(inspector.getByLabel("Font weight", { exact: true })).toHaveValue("500");
    await inspector.getByLabel("Font weight", { exact: true }).selectOption("900");
    await inspector.getByLabel("Font width", { exact: true }).fill("125");
    await expect(rail.getByRole("button", { name: "Split screen", exact: true })).toHaveCount(0);
    await inspector.locator("summary").filter({ hasText: "Layout & safe area" }).click();
    const automatic = inspector.getByRole("switch", { name: "Multiple screens", exact: true });
    await expect(automatic).toBeChecked();
    await automatic.uncheck();
    await expect(dialog.locator(".split-video-canvas")).toHaveCount(0);
    await automatic.check();
    await expect(dialog.locator(".split-panel-drag")).toHaveCount(0);
    await expect(dialog.locator(".split-video-canvas")).toBeVisible();
    const preview = await page.request.post(`${base}/editor-preview`, {
      headers, data: { title: "Check automatic", start_ms: 0, end_ms: 4000, render_config: { layout: "auto" } },
    });
    expect(preview.ok(), await preview.text()).toBeTruthy();
    expect((await preview.json()).plan.scenes.map((scene: { layout: string }) => scene.layout)).toEqual(["single", "grid"]);
    // Preview uses one source playback clock regardless of panel count.
    await expect(dialog.locator(".composition-stage video")).toHaveCount(1);
    await dialog.getByLabel("Preview timeline", { exact: true }).fill("0.6");
    await expect(dialog.locator(".live-caption")).toBeVisible();
    await expect(dialog.locator(".live-caption")).toContainText("black");
    await dialog.getByLabel("Preview timeline", { exact: true }).fill("1.4");
    await expect(dialog.locator(".live-caption")).toHaveCount(0);
    await dialog.getByLabel("Preview timeline", { exact: true }).fill("2.6");
    await expect(dialog.locator(".live-caption")).toBeVisible();
    await expect(dialog.locator(".live-caption")).toContainText("wide");
    await dialog.getByLabel("Preview timeline", { exact: true }).fill("3.8");
    await expect(dialog.locator(".live-caption")).toHaveCount(0);
    await dialog.getByLabel("Preview timeline", { exact: true }).fill("2");
    await expect.poll(() => dialog.locator(".composition-stage video").evaluate((node) => (node as HTMLVideoElement).currentTime)).toBe(2);
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
    }
    await dialog.screenshot({ path: "../../.local/split-screen-editor.png" });
    await dialog.getByRole("button", { name: "Save edits", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    const saved = (await (await page.request.get(`${base}/clips`)).json()).find((item: { id: string }) => item.id === clip.id);
    expect(saved.caption_config).toMatchObject({ font: "Urbanist", weight: 900, font_width: 125 });
    expect(saved.render_config.layout).toBe("auto");
    expect(saved.render_config.panels).toHaveLength(0);
    await page.getByRole("button", { name: "Edit clip", exact: true }).click();
    await expect(inspector.getByLabel("Font weight", { exact: true })).toHaveValue("900");
    await inspector.locator("summary").filter({ hasText: "Layout & safe area" }).click();
    await expect(inspector.getByRole("switch", { name: "Multiple screens", exact: true })).toBeChecked();
    await rail.getByRole("button", { name: "Export", exact: true }).click();
    await dialog.getByRole("button", { name: "Render 4-second preview", exact: true }).click();
    await expect(dialog.getByLabel("Rendered style preview", { exact: true })).toBeVisible({ timeout: 90_000 });
    // Existing automatic renders from the previous detector must regenerate
    // even when the user hasn't changed the clip revision.
    const renderClip = async () => {
      const result = await page.request.post(`${base}/clips/${clip.id}/render`, { headers });
      expect(result.ok(), await result.text()).toBeTruthy();
      const jobId = (await result.json()).job_id;
      await expect.poll(async () => (await (await page.request.get(`${base}/jobs`)).json()).find((job: { id: string }) => job.id === jobId)?.status, { timeout: 90_000 }).toBe("SUCCEEDED");
    };
    await renderClip();
    execFileSync("docker", ["compose", "exec", "-T", "api", "python", "-c", `
import uuid
from clipforge_api.db import SessionLocal
from clipforge_api.models import Clip
with SessionLocal() as db:
    clip = db.get(Clip, uuid.UUID('${clip.id}'))
    plan = dict(clip.crop_plan)
    plan['quality'] = {key: value for key, value in plan['quality'].items() if key != 'collage_detector'}
    clip.crop_plan = plan
    db.commit()
`], { cwd: path.resolve("../.."), timeout: 30_000 });
    await renderClip();
    const updated = (await (await page.request.get(`${base}/clips`)).json()).find((item: { id: string }) => item.id === clip.id);
    expect(updated.crop_plan.quality.collage_detector).toBe("yunet-collage-v1");
    expect(updated.crop_plan.scenes.map((scene: { layout: string }) => scene.layout)).toEqual(["single", "grid"]);
  } finally {
    if (projectId) await page.request.delete(`${api}/projects/${projectId}`, { headers });
  }
});
