export const CAPTION_FONTS = [
  "DejaVu Sans",
  "Noto Sans",
  "Bebas Neue",
  "Lato",
  "Montserrat",
  "Open Sans",
  "Roboto",
] as const;

export type CaptionStyle = {
  enabled?: boolean;
  style?: string;
  template_id?: string | null;
  font?: string;
  punctuation?: boolean;
  remove_special_characters?: boolean;
  weight?: number;
  size?: number;
  primary_color?: string;
  highlight_color?: string;
  outline?: number;
  stroke_color?: string;
  shadow?: number;
  spacing?: number;
  uppercase?: boolean;
  highlight?: boolean;
  max_words?: number;
  max_chars_per_line?: number;
  lines?: number;
  background?: boolean;
  background_color?: string;
  background_opacity?: number;
  animation?: string;
  x?: number;
  y?: number;
  width?: number;
  alignment?: string;
  safe_bottom?: number;
  position?: string;
  cues?: { start_ms: number; end_ms: number; text: string }[] | null;
};
export type OverlayStyle = {
  title?: string;
  watermark?: string;
  title_style?: string;
  logo_enabled?: boolean;
  logo_asset_id?: string | null;
  logo_position?: string;
  logo_size?: number;
  logo_opacity?: number;
  logo_margin?: number;
  logo_x?: number | null;
  logo_y?: number | null;
};
export type FramingStyle = {
  quality?: string;
  crop_mode?: string;
  anchor_x?: number | null;
  anchor_y?: number | null;
  zoom?: number;
  eye_line?: number;
  headroom?: number;
  subject?: string;
  lock_camera?: boolean;
  minimum_framing_score?: number;
  minimum_crop_hold_seconds?: number;
  horizontal_dead_zone?: number;
  vertical_dead_zone?: number;
};
export type Template = {
  id: string;
  name: string;
  category: string;
  config: CaptionStyle;
};
export type Library = {
  items: Template[];
  favorites: string[];
  recent: string[];
  default: string | null;
};
export type PreviewData = {
  source_url: string;
  logo_url: string | null;
  debug_allowed: boolean;
  plan: {
    source_width: number;
    source_height: number;
    crop_width: number;
    crop_height: number;
    output_width: number;
    output_height: number;
    keyframes: { time: number; x: number; y: number; cut: boolean }[];
    warnings: string[];
    quality: {
      score?: number | null;
      reason?: string;
      clipped_fraction?: number;
    };
    subjects: {
      time: number;
      x: number;
      y: number;
      w: number;
      h: number;
      eye_y?: number;
      subject: string;
      scene_start: number;
    }[];
  };
  segments: {
    start: number;
    end: number;
    text: string;
    words: { start: number; end: number; text: string }[];
  }[];
};
