// Only a fixed, server-configured API is reachable through this gateway.
// Cookies, CSRF Origin checks and backend authorization remain in force.
export async function proxyApi(request: Request, segments: string[]) {
  if (
    segments.some(
      (part) => !part || part === "." || part === ".." || /[\\/]/.test(part),
    )
  )
    return Response.json({ detail: "Invalid API path." }, { status: 400 });
  const incoming = new URL(request.url);
  const base = (
    process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const url = `${base}/api/v1/${segments.map(encodeURIComponent).join("/")}${incoming.search}`;
  const headers = new Headers();
  for (const name of [
    "cookie",
    "origin",
    "content-type",
    "accept",
    "range",
    "if-range",
  ])
    if (request.headers.has(name))
      headers.set(name, request.headers.get(name)!);
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body:
        request.method === "GET" || request.method === "HEAD"
          ? undefined
          : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(30_000)]),
    });
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of [
      "content-type",
      "content-disposition",
      "content-range",
      "accept-ranges",
      "x-request-id",
      "retry-after",
    ])
      if (upstream.headers.has(name))
        responseHeaders.set(name, upstream.headers.get(name)!);
    for (const cookie of upstream.headers.getSetCookie())
      responseHeaders.append("Set-Cookie", cookie);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        detail:
          "The API service is temporarily unavailable. Check the clip status before retrying a render.",
      },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
