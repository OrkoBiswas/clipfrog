// Browser requests use the page's origin. The server gateway resolves the API
// at runtime, avoiding cross-origin cookies, IPv6 and stale build-time URLs.
export const API_URL = "";
export type User = {
  id: string;
  name: string;
  email: string;
  email_verified: boolean;
  is_admin?: boolean;
};
export type Config = {
  clip_count: number;
  duration_min: number;
  duration_max: number;
  ratios: string[];
  captions: boolean;
  caption_style: string;
  crop_mode: string;
  quality: string;
  keywords?: string[];
  minimum_score?: number;
  minimum_separation?: number;
  max_overlap?: number;
  semantic_ranking?: boolean;
  brand_kit_id?: string | null;
  caption_config?: import("./editor-types").CaptionStyle | null;
  render_config?: import("./editor-types").FramingStyle | null;
  platform_preset?: string;
};
export type Project = {
  id: string;
  name: string;
  content_type: string;
  language: string;
  status: string;
  source_asset_id: string | null;
  processing_config: Config;
  brand_config: Partial<import("@/components/brand-kits").BrandConfig>;
  owner_email?: string | null;
  created_at: string;
  updated_at: string;
};
export type Stats = {
  clips_created: number;
  projects: number;
  storage_bytes: number;
  processing_jobs: number;
  minutes_processed: number;
};

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    options.body &&
    !headers.has("Content-Type") &&
    !(options.body instanceof FormData)
  )
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...options,
      credentials: "include",
      cache: "no-store",
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new Error(
      "Could not connect to the app. Check your connection and refresh the page. If you were rendering, check the clip status before retrying.",
    );
  }
  if (!response.ok) {
    const body: { detail?: string | { msg: string }[] } = await response
      .json()
      .catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((v) => v.msg).join(". ")
          : `Request failed (${response.status})`,
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
