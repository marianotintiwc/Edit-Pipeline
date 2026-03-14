export type ClipType = "scene" | "broll" | "endcard" | "introcard";
export type SubtitleMode = "auto" | "manual" | "none";

export interface ClipInput {
  type: ClipType;
  url: string;
  start_time?: number;
  end_time?: number;
  alpha_fill?: Record<string, unknown> | null;
  overlap_seconds?: number;
  effects?: Record<string, unknown> | null;
}

export interface JobInput {
  video_urls?: string[];
  geo?: string;
  clips: ClipInput[];
  music_url?: string | null;
  music_volume?: number;
  loop_music?: boolean;
  subtitle_mode?: SubtitleMode;
  edit_preset?: string;
  enable_interpolation?: boolean;
  rife_model?: string;
  input_fps?: number;
  manual_srt_url?: string;
  style_overrides?: Record<string, unknown> | null;
  output_filename?: string;
  output_folder?: string;
  output_bucket?: string;
  aspect_ratio?: string;
  request_text?: string;
  plan_only?: boolean;
  storyboard?: Record<string, unknown> | null;
  retrieval?: Record<string, unknown> | null;
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface WizardStep {
  id: string;
  title: string;
}

export interface ConfigOptions {
  geos: SelectOption[];
  subtitleModes: SelectOption[];
  editPresets: SelectOption[];
  clipTypes: SelectOption[];
  wizardSteps: WizardStep[];
}

export interface PresetListItem {
  name: string;
  label: string;
  description?: string;
  recommended_for?: string;
}

export interface PresetListResponse {
  items: PresetListItem[];
}

export interface PresetDetail {
  name: string;
  label: string;
  description?: string;
  recommended_for?: string;
  basic_fields?: string[];
  advanced_fields?: string[];
  input: JobInput;
}

export interface JobPreviewResponse {
  normalized_input: JobInput;
  job_input: JobInput;
  intents: string[];
  warnings: string[];
  plan_only: boolean;
  resolved_style: Record<string, unknown>;
  resolved_clips: ClipInput[];
  storyboard_plan?: Record<string, unknown> | null;
  retrieval_plan?: Record<string, unknown> | null;
  execution_steps: string[];
}

export interface JobSubmitResponse {
  run_id?: string;
  job_id?: string;
  status: string;
  warnings?: string[];
  preview?: JobPreviewResponse;
}

export interface JobStatusResponse {
  status: string;
  stage?: string;
  logs?: string[];
  output?: {
    output_url?: string;
  };
}

export interface RunListItem {
  run_id: string;
  job_id: string;
  status: string;
  geo?: string;
  preset_name?: string | null;
  created_at?: string;
  updated_at?: string;
  output_url?: string;
}

export interface RunsListResponse {
  items: RunListItem[];
}

export interface RunDetail extends RunListItem {
  logs?: string[];
  stage?: string;
  input_snapshot?: JobInput;
}

export type BatchRowStatus =
  | "ready"
  | "blocked_by_validation"
  | "submitted"
  | "queued"
  | "in_progress"
  | "completed"
  | "failed";

export interface BatchRowResult {
  row_number: number;
  status: BatchRowStatus;
  warnings: string[];
  errors: string[];
  input?: JobInput;
  run_id?: string;
  job_id?: string;
}

export interface BatchDetail {
  batch_id: string;
  filename: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  submitted_rows?: number;
  created_at?: string;
  updated_at?: string;
  rows: BatchRowResult[];
}

export interface BatchListItem {
  batch_id: string;
  filename: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  submitted_rows?: number;
  created_at?: string;
  updated_at?: string;
}

export interface BatchListResponse {
  items: BatchListItem[];
}
