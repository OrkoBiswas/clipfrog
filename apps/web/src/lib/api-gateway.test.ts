import { afterEach, describe, expect, it, vi } from "vitest";
import { proxyApi } from "./api-gateway";
import { api } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("same-origin API gateway", () => {
  it("forwards render body, cookies and the original CSRF origin exactly once", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    const fetcher = vi
      .fn()
      .mockResolvedValue(Response.json({ job_id: "job" }, { status: 202 }));
    vi.stubGlobal("fetch", fetcher);
    const result = await proxyApi(
      new Request("http://127.0.0.1:3000/api/v1/projects/p/clip-actions?x=1", {
        method: "POST",
        headers: {
          Origin: "http://127.0.0.1:3000",
          Cookie: "session=test",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "render", clip_ids: ["c"] }),
      }),
      ["projects", "p", "clip-actions"],
    );
    expect(result.status).toBe(202);
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("http://api:8000/api/v1/projects/p/clip-actions?x=1");
    expect(options.headers.get("origin")).toBe("http://127.0.0.1:3000");
    expect(options.headers.get("cookie")).toBe("session=test");
    expect(JSON.parse(new TextDecoder().decode(options.body))).toEqual({
      action: "render",
      clip_ids: ["c"],
    });
  });
  it("preserves sign-in cookies and real API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { detail: "Wait for the current operation to finish." },
            {
              status: 409,
              headers: {
                "Set-Cookie":
                  "clipforge_session=test; HttpOnly; Path=/; SameSite=Lax",
                "X-Request-ID": "request",
              },
            },
          ),
        ),
    );
    const result = await proxyApi(
      new Request("http://localhost:3000/api/v1/me"),
      ["me"],
    );
    expect(result.status).toBe(409);
    expect(result.headers.get("set-cookie")).toContain("HttpOnly");
    expect(result.headers.get("x-request-id")).toBe("request");
    expect((await result.json()).detail).toContain("current operation");
  });
  it("returns a readable 502 instead of a browser fetch failure, without retrying mutations", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetcher);
    const result = await proxyApi(
      new Request("http://localhost:3000/api/v1/render", { method: "POST" }),
      ["render"],
    );
    expect(result.status).toBe(502);
    expect((await result.json()).detail).toContain("Check the clip status");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("cannot redirect the fixed upstream using path traversal", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(
      (
        await proxyApi(new Request("http://localhost:3000/api/v1/me"), [
          "..",
          "admin",
        ])
      ).status,
    ).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("browser API errors", () => {
  it("uses the page origin and preserves validation errors", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { detail: "Render this clip before previewing it." },
          { status: 409 },
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    await expect(api("/projects/p/clips/c/media")).rejects.toThrow(
      "Render this clip",
    );
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/projects/p/clips/c/media");
    expect(fetcher.mock.calls[0][1].headers.has("content-type")).toBe(false);
  });
  it("explains network failures without silently resubmitting renders", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetcher);
    await expect(
      api("/projects/p/clips/c/render", { method: "POST" }),
    ).rejects.toThrow("check the clip status before retrying");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
