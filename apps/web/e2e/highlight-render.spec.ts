import { expect, test, type APIResponse } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

type Job = { id: string; status: string; error_message: string | null };

async function json<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<T>;
}

test("analyze speech, find highlights and render playable clips through the app origin", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(600_000);
  const fixture = path.resolve("../../.local/speech.mp4");
  test.skip(!fs.existsSync(fixture), "Provide .local/speech.mp4 as described in README.md.");
  const origin = new URL(baseURL!).origin;
  const headers = { Origin: origin };
  let projectId = "";
  const failedRequests: string[] = [];
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/v1/"))
      failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`);
  });

  async function waitForJob(jobId: string, timeout = 120_000) {
    let job: Job | undefined;
    await expect.poll(async () => {
      const jobs = await json<Job[]>(
        await page.request.get(`/api/v1/projects/${projectId}/jobs`),
      );
      job = jobs.find((item) => item.id === jobId);
      return job?.status;
    }, { timeout, intervals: [1000, 2000] }).toMatch(/^(SUCCEEDED|FAILED|CANCELED)$/);
    expect(job?.status, job?.error_message ?? `Job ${jobId} did not succeed`).toBe("SUCCEEDED");
  }

  async function clickAndWaitForJob(buttonName: string | RegExp, endpoint: string, timeout?: number) {
    const responsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === endpoint,
    );
    await page.getByRole("button", { name: buttonName, exact: true }).click();
    const response = await responsePromise;
    expect(new URL(response.url()).origin).toBe(origin);
    expect(response.status(), await response.text()).toBe(202);
    const result = await response.json() as { job_id: string; clip_ids?: string[] };
    await waitForJob(result.job_id, timeout);
    return result;
  }

  try {
    await json(await page.request.post("/api/v1/auth/register", {
      headers,
      data: {
        name: "Highlight render test",
        email: `highlight-render-${Date.now()}@example.com`,
        password: "highlight-render-test-password",
      },
    }));
    const project = await json<{ id: string }>(await page.request.post("/api/v1/projects", {
      headers,
      data: {
        name: "Highlight render regression",
        language: "en",
        processing_config: {
          clip_count: 1,
          duration_min: 5,
          duration_max: 12,
          minimum_score: 0,
          ratios: ["9:16"],
          quality: "Draft",
          captions: true,
        },
      },
    }));
    projectId = project.id;
    const base = `/api/v1/projects/${projectId}`;
    const file = fs.readFileSync(fixture);
    const upload = await json<{ id: string; part_count: number; part_size: number }>(
      await page.request.post(`${base}/upload/initiate`, {
        headers,
        data: { filename: "speech.mp4", size_bytes: file.length, mime_type: "video/mp4" },
      }),
    );
    for (let part = 1; part <= upload.part_count; part++) {
      const signed = await json<{ url: string }>(await page.request.post(
        `${base}/upload/${upload.id}/parts/${part}`, { headers },
      ));
      const uploaded = await page.request.put(signed.url, {
        data: file.subarray((part - 1) * upload.part_size, part * upload.part_size),
      });
      expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
    }
    const probe = await json<{ job_id: string }>(await page.request.post(
      `${base}/upload/${upload.id}/complete`, { headers },
    ));
    await waitForJob(probe.job_id);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByRole("heading", { name: "Step 2: Analyze your video", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Find highlights", exact: true })).toBeDisabled();
    await clickAndWaitForJob("Analyze video", `${base}/analyze`, 300_000);
    await expect(page.getByText("Analysis complete.", { exact: false })).toBeVisible({ timeout: 15_000 });
    const transcriptDetails = page.locator("details").filter({ has: page.locator("summary", { hasText: "Read or download the transcript" }) });
    await expect(transcriptDetails).not.toHaveAttribute("open", "");
    await transcriptDetails.locator("summary").click();
    await expect(page.getByRole("link", { name: "Download TXT", exact: true })).toBeVisible();
    await transcriptDetails.locator("summary").click();
    await expect(page.getByRole("button", { name: "Find highlights", exact: true }))
      .toBeVisible({ timeout: 15_000 });
    await clickAndWaitForJob("Find highlights", `${base}/highlights`);
    await expect(page.getByRole("button", { name: "Render 1 clip", exact: true }))
      .toBeVisible({ timeout: 15_000 });
    const highlighted = await json<{
      engine: { mode: string; version: string };
      items: { id: string; can_rate: boolean; start_ms: number; end_ms: number }[];
      learning: { status: string };
    }>(await page.request.get(`${base}/highlights`));
    expect(highlighted.engine.mode).toBe("local");
    expect(highlighted.engine.version).toBe("local-editorial-v3");
    expect(highlighted.items[0].can_rate).toBe(true);
    const review = page.getByRole("group", { name: "Review highlight 1" });
    await review.getByRole("button", { name: "Preview moment", exact: true }).click();
    const sourcePreview = page.getByLabel("Highlight 1 preview", { exact: true });
    await expect(sourcePreview).toBeVisible();
    await expect.poll(() => sourcePreview.evaluate((element: HTMLVideoElement) => element.readyState))
      .toBeGreaterThanOrEqual(2);
    await expect.poll(() => sourcePreview.evaluate((element: HTMLVideoElement) => element.currentTime))
      .toBeGreaterThanOrEqual(highlighted.items[0].start_ms / 1000 - 0.1);
    await review.getByRole("button", { name: "Poor clip", exact: true }).click();
    await expect(review.getByRole("button", { name: "Poor clip", exact: true }))
      .toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: "Render 1 clip", exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("button", { name: "Poor clip", exact: true }))
      .toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Good clip", exact: true }).click();
    await expect(page.getByRole("button", { name: "Good clip", exact: true }))
      .toHaveAttribute("aria-pressed", "true");
    const rated = await json<{ learning: { good_ratings: number; poor_ratings: number } }>(await page.request.get(`${base}/highlights`));
    expect(rated.learning.good_ratings).toBe(1);
    expect(rated.learning.poor_ratings).toBe(0);
    const render = await clickAndWaitForJob("Render 1 clip", `${base}/clips/generate`);
    expect(render.clip_ids).toHaveLength(1);

    const clips = await json<{
      id: string;
      title: string;
      status: string;
      output_asset_id: string | null;
      revision: number;
      rendered_revision: number | null;
      caption_config: { enabled: boolean };
    }[]>(await page.request.get(`${base}/clips`));
    expect(clips).toHaveLength(1);
    expect(clips[0].id).toBe(render.clip_ids![0]);
    expect(clips[0].status).toBe("COMPLETED");
    expect(clips[0].output_asset_id).toBeTruthy();
    expect(clips[0].rendered_revision).toBe(clips[0].revision);
    expect(clips[0].caption_config.enabled).toBe(true);

    await page.getByRole("tab", { name: "Clips", exact: true }).click();
    const preview = page.getByRole("button", { name: `Preview ${clips[0].title}`, exact: true });
    await expect(preview).toBeVisible({ timeout: 15_000 });
    await preview.click();
    const video = page.locator(".studio-clip-card video");
    await expect(video).toBeVisible();
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState))
      .toBeGreaterThanOrEqual(2);
    expect(await video.evaluate((element: HTMLVideoElement) => element.videoWidth)).toBeGreaterThan(0);
    await video.evaluate((element: HTMLVideoElement) => element.play());
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime))
      .toBeGreaterThan(0.2);
    await video.evaluate((element: HTMLVideoElement) => element.pause());
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: `Download ${clips[0].title} MP4`, exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.mp4$/);
    expect(await download.failure()).toBeNull();
    expect(failedRequests).toEqual([]);
    await expect(page.getByText("Failed to fetch", { exact: true })).toHaveCount(0);
  } finally {
    if (projectId) await page.request.delete(`/api/v1/projects/${projectId}`, { headers });
  }
});
