import type { JobInput } from "../types";

export interface Recipe {
  id: string;
  label: string;
  description: string;
  input: Partial<JobInput>;
}

export const CURATED_RECIPES: Recipe[] = [
  {
    id: "meli-quick-start",
    label: "MELI Quick Start",
    description: "Balanced defaults for fast launch and clean subtitles.",
    input: {
      geo: "MLB",
      subtitle_mode: "auto",
      edit_preset: "standard_vertical",
      clips: [
        { type: "introcard", url: "https://example.com/intro.mov" },
        { type: "scene", url: "https://example.com/scene1.mp4" },
      ],
      music_url: "random",
    },
  },
  {
    id: "review-safe-plan",
    label: "Review-safe Plan",
    description: "Plan-only profile for quick validation before queueing.",
    input: {
      geo: "MLA",
      subtitle_mode: "auto",
      plan_only: true,
      clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
    },
  },
];
