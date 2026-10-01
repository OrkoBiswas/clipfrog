export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
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
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
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
