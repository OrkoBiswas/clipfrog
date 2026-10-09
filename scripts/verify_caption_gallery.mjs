// Isolated UI verification. All API data is in memory; never touches the live workspace.
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, ".local/caption-collection");
await fs.mkdir(output, { recursive: true });
const source = await fs.readFile(
  path.join(root, "apps/web/src/lib/caption-templates.ts"),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { CAPTION_TEMPLATES } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);
await fs.writeFile(
  path.join(output, "presets.json"),
  JSON.stringify(CAPTION_TEMPLATES, null, 2),
);
const user = {
  id: "isolated-caption-preview",
  name: "Caption Studio",
  email: "preview@example.test",
  email_verified: true,
  is_admin: false,
};
const projects = [
  {
    id: "preview-project",
    name: "Isolated preview",
    content_type: "Podcast",
    status: "UPLOADED",
    source_asset_id: "source",
    created_at: "2026-10-01",
    processing_config: { ratios: ["9:16"] },
  },
];
const clips = [
  {
    id: "preview-clip",
    title: "Preview clip",
    start_ms: 0,
    end_ms: 3000,
    aspect_ratio: "9:16",
    caption_config: {
      cues: [{ start_ms: 0, end_ms: 3000, text: "Keep these words" }],
    },
  },
];
let applied;
const backend = createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "http://localhost:3100");
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Content-Type", "application/json");
  if (req.method === "OPTIONS") {
    res.end();
    return;
  }
  let result = [];
  if (req.url === "/api/v1/me") result = user;
  if (req.url === "/api/v1/projects") result = projects;
  if (req.url === "/api/v1/projects/preview-project/clips") result = clips;
  if (req.url === "/api/v1/usage")
    result = { plan: "free", usage: {}, allowance: {}, administrator: false };
  if (req.url === "/api/v1/projects/preview-project/clip-actions") {
    let body = "";
    for await (const chunk of req) body += chunk;
    applied = JSON.parse(body);
    const cues = clips[0].caption_config.cues;
    clips[0].caption_config = { ...applied.caption_config, cues };
    result = { affected: 1 };
  }
  res.end(JSON.stringify(result));
});
await new Promise((resolve) => backend.listen(8101, "127.0.0.1", resolve));
// A separate port and an in-memory API keep this verification away from the live stack.
const next = spawn(
  process.execPath,
  [path.join(root, "node_modules/next/dist/bin/next"), "dev", "--port", "3100"],
  {
    cwd: path.join(root, "apps/web"),
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      CAPTION_VERIFY: "1",
      API_INTERNAL_URL: "http://127.0.0.1:8101",
      NEXT_PUBLIC_API_URL: "http://localhost:8101",
    },
  },
);
let serverLog = "";
next.stdout.on("data", (data) => {
  serverLog += data;
});
next.stderr.on("data", (data) => {
  serverLog += data;
});
let browser;
try {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try {
      if (
        (
          await fetch("http://localhost:3100/templates", {
            signal: AbortSignal.timeout(15000),
          })
        ).ok
      ) {
        ready = true;
        break;
      }
    } catch {}
    if (next.exitCode !== null) throw new Error(serverLog);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!ready) throw new Error(serverLog);
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://localhost:3100/templates");
  await expect(page.locator(".ct-card")).toHaveCount(24);
  await expect(page.getByText("Free plan", { exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(
    page.getByRole("link", { name: "Templates", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(output, "gallery-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Karaoke", exact: true }).click();
  await expect(page.locator(".ct-card")).toHaveCount(3);
  await page.getByRole("button", { name: "All styles", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Search caption templates" })
    .fill("Bebas");
  await expect(page.locator(".ct-card")).toHaveCount(3);
  await page
    .getByRole("textbox", { name: "Search caption templates" })
    .fill("");
  await page
    .getByRole("button", { name: "Preview Studio Rise", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Customize Studio Rise" });
  await expect(dialog).toBeVisible();
  await dialog
    .getByLabel("Font family", { exact: true })
    .selectOption("Montserrat");
  await dialog
    .getByLabel("Animation", { exact: true })
    .selectOption("word-pill");
  await dialog
    .getByLabel("Word display", { exact: true })
    .selectOption("build");
  await dialog.getByLabel("Spoken word size", { exact: true }).fill("1.12");
  await dialog.getByLabel("Font size", { exact: true }).fill("72");
  await dialog
    .locator("summary")
    .filter({ hasText: "Edit sample text" })
    .click();
  await dialog
    .getByRole("button", { name: "Seek to word 1: Every", exact: true })
    .click();
  const liveWords = dialog.locator(".caption-player-caption [data-word-index]");
  await expect(liveWords.filter({ hasText: "Every" })).toHaveAttribute(
    "data-active",
    "true",
  );
  await expect(liveWords.filter({ hasText: "great" })).toHaveCSS(
    "opacity",
    "0",
  );
  await dialog
    .getByRole("button", { name: "Seek to word 2: great", exact: true })
    .click();
  await expect(liveWords.filter({ hasText: "great" })).toHaveAttribute(
    "data-active",
    "true",
  );
  await expect(liveWords.filter({ hasText: "Every" })).toHaveCSS(
    "opacity",
    "1",
  );
  await dialog
    .getByLabel("Word display", { exact: true })
    .selectOption("single");
  await expect(liveWords).toHaveCount(1);
  await expect(liveWords).toHaveText("great");
  await dialog
    .getByLabel("Word display", { exact: true })
    .selectOption("build");
  await dialog.getByText("Save your own preset", { exact: true }).click();
  await dialog.getByLabel("Preset name").fill("Signature test");
  await dialog
    .getByRole("button", { name: "Save preset", exact: true })
    .click();
  await expect(
    dialog.getByText("“Signature test” saved to My presets."),
  ).toBeVisible();
  await dialog
    .getByLabel("Project", { exact: true })
    .selectOption("preview-project");
  await dialog.getByRole("checkbox", { name: /Preview clip/ }).check();
  await dialog.getByRole("button", { name: "Apply to 1 clip" }).click();
  await expect(dialog.getByText(/Style saved to 1 clip/)).toBeVisible();
  expect(applied.caption_config).toMatchObject({
    font: "Montserrat",
    size: 72,
    animation: "word-pill",
    word_display: "build",
    active_scale: 1.12,
  });
  expect(clips[0].caption_config.cues[0].text).toBe("Keep these words");
  await dialog.evaluate((el) => el.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, "customize-desktop.png") });
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.reload();
  await page.getByRole("button", { name: "My presets", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Signature test", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "All styles", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(output, "gallery-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Preview Neon Focus", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Customize Neon Focus" }),
  ).toBeVisible();
  expect(
    await page
      .locator(".ct-customize-dialog")
      .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
  await page.screenshot({ path: path.join(output, "customize-mobile.png") });
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  await expect(page.getByLabel("Font family", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Use on clips", exact: true }).click();
  await expect(page.getByLabel("Project", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(
    page.getByLabel("Play caption preview", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.evaluate(() =>
    document.documentElement.setAttribute("data-theme", "light"),
  );
  await page.screenshot({
    path: path.join(output, "gallery-light.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  console.log(
    "Caption gallery verified: 24 presets, filters, customization, browser persistence, apply-to-clip, responsive layouts, reduced motion, no runtime errors.",
  );
} finally {
  await browser?.close();
  next.kill();
  backend.closeAllConnections();
  await new Promise((resolve) => backend.close(resolve));
}
