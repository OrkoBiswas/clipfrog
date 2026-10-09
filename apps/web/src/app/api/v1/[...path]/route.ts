import { proxyApi } from "@/lib/api-gateway";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function handler(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxyApi(request, path);
}

export {
  handler as GET,
  handler as HEAD,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};
