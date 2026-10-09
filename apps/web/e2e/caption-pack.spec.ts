import { expect, test } from "@playwright/test";

test("removed MOGRT caption values normalize to basic subtitles", async ({
  page,
}) => {
  const api = "http://localhost:8000/api/v1";
  const headers = { Origin: "http://localhost:3000" };
  const registration = await page.request.post(`${api}/auth/register`, {
    headers,
    data: {
      name: "Basic Caption Creator",
      email: `basic-caption-api-${Date.now()}@example.com`,
      password: "test-long-password-123",
    },
  });
  expect(registration.ok()).toBeTruthy();

  const templates = await page.request.get(`${api}/caption-templates`);
  expect(templates.status()).toBe(404);

  const response = await page.request.post(`${api}/projects`, {
    headers,
    data: {
      name: "Basic subtitle compatibility",
      processing_config: {
        caption_config: {
          animation: "mogrt-pack1-01",
          style: "Bold",
        },
      },
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const project = await response.json();
  expect(project.processing_config.caption_config.animation).toBe("word-pop");
  expect(project.processing_config.caption_config.style).toBe("Bold");
  await page.request.delete(`${api}/projects/${project.id}`, { headers });
});
