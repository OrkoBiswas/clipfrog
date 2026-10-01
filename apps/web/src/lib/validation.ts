import { z } from "zod";
export const projectSchema = z
  .object({
    name: z.string().trim().min(1, "Give your project a name").max(160),
    content_type: z.enum([
      "Auto",
      "Podcast",
      "Interview",
      "Talking Head",
      "Tutorial",
      "Webinar",
      "Gaming",
      "Presentation",
      "Other",
    ]),
    language: z.string().min(2).max(20),
    clip_count: z.number().int().min(1).max(100),
    duration_min: z.number().int().min(5).max(180),
    duration_max: z.number().int().min(5).max(180),
    ratios: z.array(z.string()).min(1, "Choose at least one ratio"),
    captions: z.boolean(),
    keywords: z.string().max(500).optional(),
    minimum_score: z.number().min(0).max(100).optional(),
    minimum_separation: z.number().min(0).max(180).optional(),
    max_overlap: z.number().min(0).max(1).optional(),
    semantic_ranking: z.boolean().optional(),
  })
  .refine((v) => v.duration_max >= v.duration_min, {
    message: "Maximum must be at least the minimum duration",
    path: ["duration_max"],
  });
export type ProjectFormValues = z.infer<typeof projectSchema>;
