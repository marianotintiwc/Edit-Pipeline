import type {
  BatchDetail,
  BatchListResponse,
  ConfigOptions,
  JobInput,
  JobPreviewResponse,
  JobStatusResponse,
  JobSubmitResponse,
  PresetDetail,
  PresetListResponse,
  RunDetail,
  RunsListResponse,
} from "./types";

function getApiUrl(path: string): string {
  return `${import.meta.env.VITE_API_BASE_URL ?? ""}${path}`;
}

async function readJson<T>(response: Response): Promise<T> {
  const rawBody = await response.text();
  let data = {} as T & { errors?: string[]; detail?: string; error_code?: string };
  if (rawBody) {
    try {
      data = JSON.parse(rawBody) as T & { errors?: string[]; detail?: string; error_code?: string };
    } catch (error) {
      throw new Error(
        response.ok
          ? "Server returned malformed JSON"
          : `Request failed with malformed JSON (${response.status})`,
      );
    }
  }

  if (!response.ok) {
    if (Array.isArray(data.errors) && data.errors.length > 0) {
      throw new Error(data.errors.join(", "));
    }
    if (typeof data.detail === "string") {
      throw new Error(data.detail);
    }
    if (typeof data.error_code === "string") {
      throw new Error(data.error_code);
    }
    throw new Error("Request failed");
  }
  return data as T;
}

export async function submitJob(input: JobInput): Promise<JobSubmitResponse> {
  const response = await fetch(getApiUrl("/api/jobs"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ input }),
  });

  return readJson<JobSubmitResponse>(response);
}

export async function previewJob(input: JobInput): Promise<JobPreviewResponse> {
  const response = await fetch(getApiUrl("/api/jobs/preview"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ input }),
  });

  return readJson<JobPreviewResponse>(response);
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(getApiUrl(`/api/jobs/${jobId}`), {
    credentials: "include",
  });
  return readJson<JobStatusResponse>(response);
}

export async function getConfigOptions(): Promise<ConfigOptions> {
  const response = await fetch(getApiUrl("/api/config/options"), {
    credentials: "include",
  });
  return readJson<ConfigOptions>(response);
}

export async function getPresets(): Promise<PresetListResponse> {
  const response = await fetch(getApiUrl("/api/presets"), {
    credentials: "include",
  });
  return readJson<PresetListResponse>(response);
}

export async function getPreset(name: string): Promise<PresetDetail> {
  const response = await fetch(getApiUrl(`/api/presets/${name}`), {
    credentials: "include",
  });
  return readJson<PresetDetail>(response);
}

export async function listRuns(): Promise<RunsListResponse> {
  const response = await fetch(getApiUrl("/api/runs"), {
    credentials: "include",
  });
  return readJson<RunsListResponse>(response);
}

export async function getRun(runId: string): Promise<RunDetail> {
  const response = await fetch(getApiUrl(`/api/runs/${runId}`), {
    credentials: "include",
  });
  return readJson<RunDetail>(response);
}

export async function createBatchFromCsv(
  file: File,
  options?: { mapping?: Record<string, string>; recipeInput?: Record<string, unknown> | null },
): Promise<BatchDetail> {
  const formData = new FormData();
  formData.append("file", file);
  if (options?.mapping && Object.keys(options.mapping).length > 0) {
    formData.append("mapping", JSON.stringify(options.mapping));
  }
  if (options?.recipeInput) {
    formData.append("recipe_input", JSON.stringify(options.recipeInput));
  }
  const response = await fetch(getApiUrl("/api/batches"), {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  return readJson<BatchDetail>(response);
}

export async function getBatch(batchId: string): Promise<BatchDetail> {
  const response = await fetch(getApiUrl(`/api/batches/${batchId}`), {
    credentials: "include",
  });
  return readJson<BatchDetail>(response);
}

export async function listBatches(): Promise<BatchListResponse> {
  const response = await fetch(getApiUrl("/api/batches"), {
    credentials: "include",
  });
  return readJson<BatchListResponse>(response);
}

export async function submitBatch(
  batchId: string,
  options?: { recipeInput?: Record<string, unknown> | null },
): Promise<BatchDetail> {
  const response = await fetch(getApiUrl(`/api/batches/${batchId}/submit`), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ recipe_input: options?.recipeInput ?? null }),
  });
  return readJson<BatchDetail>(response);
}
