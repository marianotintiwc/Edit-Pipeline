import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { getConfigOptions, getPreset, getPresets, previewJob, submitJob } from "./api";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ValidationErrors } from "./components/ValidationErrors";
import { Shell } from "./Shell";
import { StatusBanner } from "./components/primitives";
import { BatchPage } from "./pages/BatchPage";
import { HomePage } from "./pages/HomePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { RunsPage } from "./pages/RunsPage";
import {
  StudioBriefView,
  StudioLayout,
  StudioReviewView,
  StudioStyleView,
} from "./pages/StudioPage";
import type {
  ConfigOptions,
  ClipInput,
  JobInput,
  JobPreviewResponse,
  JobSubmitResponse,
  PresetDetail,
  PresetListItem,
  Profile,
} from "./types";
import { applyProfileToForm } from "./components/ProfileSelector";

const DEFAULT_FORM: JobInput = {
  geo: "",
  clips: [],
  music_url: "random",
  music_volume: 0.3,
  loop_music: true,
  subtitle_mode: "auto",
  edit_preset: "standard_vertical",
  enable_interpolation: true,
  rife_model: "rife-v4",
  input_fps: 24,
  aspect_ratio: "9:16",
  plan_only: false,
};

function mergeFormWithDefaults(input: Partial<JobInput>): JobInput {
  return {
    ...DEFAULT_FORM,
    ...input,
    clips: input.clips ?? [],
  };
}

function AppContent() {
  const navigate = useNavigate();
  const [configOptions, setConfigOptions] = useState<ConfigOptions | null>(null);
  const [isConfigLoading, setIsConfigLoading] = useState(true);
  const [presets, setPresets] = useState<PresetListItem[]>([]);
  const [isPresetsLoading, setIsPresetsLoading] = useState(true);
  const [selectedPreset, setSelectedPreset] = useState<PresetDetail | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [form, setForm] = useState<JobInput>(() => mergeFormWithDefaults(DEFAULT_FORM));
  const [errors, setErrors] = useState<string[]>([]);
  const [preview, setPreview] = useState<JobPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [jobResult, setJobResult] = useState<JobSubmitResponse | null>(null);

  useEffect(() => {
    setIsConfigLoading(true);
    void getConfigOptions()
      .then((response) => setConfigOptions(response))
      .catch((error: Error) => setErrors((current) => [...current, error.message]))
      .finally(() => setIsConfigLoading(false));

    setIsPresetsLoading(true);
    void getPresets()
      .then((response) => setPresets(response.items))
      .catch((error: Error) => setErrors((current) => [...current, error.message]))
      .finally(() => setIsPresetsLoading(false));
  }, []);

  const updateForm = (patch: Partial<JobInput>) => {
    setForm((current) => ({ ...current, ...patch }));
    setPreview(null);
    setPreviewError(null);
  };

  const handlePresetSelection = async (presetName: string) => {
    setErrors([]);
    try {
      const preset = await getPreset(presetName);
      setSelectedPreset(preset);
      setSelectedProfile(null);
      setPreview(null);
      setPreviewError(null);
      setForm(mergeFormWithDefaults(preset.input));
      navigate("/studio/brief");
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Failed to load preset"]);
    }
  };

  const handleProfileSelect = (profile: Profile | null) => {
    setSelectedProfile(profile);
    setPreview(null);
    setPreviewError(null);
    if (profile) {
      setForm((current) => applyProfileToForm(current, profile));
    }
  };

  const handleClipsChange = (clips: ClipInput[]) => {
    setForm((current) => ({ ...current, clips }));
    setPreview(null);
    setPreviewError(null);
  };

  const handleAddClip = () => {
    setForm((current) => ({
      ...current,
      clips: [...current.clips, { type: "scene", url: "" }],
    }));
    setPreview(null);
    setPreviewError(null);
  };

  const canPreview = form.clips.some((clip) => clip.url.trim().length > 0);

  const handlePreview = async () => {
    if (!canPreview) {
      navigate("/studio/review");
      return;
    }

    navigate("/studio/review");
    setIsPreviewLoading(true);
    setPreviewError(null);
    try {
      const nextPreview = await previewJob(form);
      setPreview(nextPreview);
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : "Failed to prepare preview");
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleLaunch = async () => {
    if (!canPreview) {
      return;
    }

    try {
      const result = await submitJob(form);
      setJobResult(result);
      if (result.preview) {
        setPreview(result.preview);
      }
      if (result.status === "PLAN_ONLY") {
        navigate("/studio/review");
      } else {
        navigate("/runs");
      }
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Failed to submit job"]);
    }
  };

  const studioProps = {
    preview,
    previewError,
    isPreviewLoading,
    presets,
    selectedPreset,
    selectedProfile,
    form,
    configOptions,
    isConfigLoading,
    isPresetsLoading,
    canPreview,
    onPresetSelect: (presetName: string) => {
      void handlePresetSelection(presetName);
    },
    onProfileSelect: handleProfileSelect,
    onFormChange: updateForm,
    onClipsChange: handleClipsChange,
    onAddClip: handleAddClip,
    onPreview: () => {
      void handlePreview();
    },
    onLaunch: () => {
      void handleLaunch();
    },
  };

  const alertSlot = (
    <>
      <ValidationErrors errors={errors} />
      {jobResult ? (
        <StatusBanner title={jobResult.status === "PLAN_ONLY" ? "Plan generated" : "Run launched"} tone="success">
          {(jobResult.warnings ?? []).map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
          {jobResult.run_id ? <p>Run ID: {jobResult.run_id}</p> : null}
          {jobResult.job_id ? <p>Job ID: {jobResult.job_id}</p> : null}
        </StatusBanner>
      ) : null}
    </>
  );

  return (
    <Shell alertSlot={alertSlot}>
      <Routes>
        <Route path="/" element={
          <HomePage
            presets={presets}
            isPresetsLoading={isPresetsLoading}
            latestJobResult={jobResult}
            onApplyRecipe={(input) => {
              setForm(mergeFormWithDefaults(input));
              setPreview(null);
              setPreviewError(null);
            }}
          />
        } />
        <Route
          path="/studio/brief"
          element={
            <StudioLayout {...studioProps}>
              <StudioBriefView {...studioProps} />
            </StudioLayout>
          }
        />
        <Route
          path="/studio/style"
          element={
            <StudioLayout {...studioProps}>
              <StudioStyleView {...studioProps} />
            </StudioLayout>
          }
        />
        <Route
          path="/studio/storyboard"
          element={
            <StudioLayout {...studioProps}>
              <PlaceholderPage
                eyebrow="Storyboard"
                title="Scene structure is queued for P2"
                description="The shell route exists now so Storyboard can land without reshaping the Studio information architecture later."
              />
            </StudioLayout>
          }
        />
        <Route
          path="/studio/edit"
          element={
            <StudioLayout {...studioProps}>
              <PlaceholderPage
                eyebrow="Edit"
                title="Clip strip and transcript editing are deferred"
                description="The Edit route is reserved for the future lightweight editing surface once the shell migration and structured controls settle."
              />
            </StudioLayout>
          }
        />
        <Route
          path="/studio/review"
          element={
            <StudioLayout {...studioProps}>
              <StudioReviewView {...studioProps} />
            </StudioLayout>
          }
        />
        <Route path="/studio" element={<Navigate to="/studio/brief" replace />} />
        <Route path="/batch" element={<Navigate to="/batch/import" replace />} />
        <Route path="/batch/:stepId" element={<BatchPage />} />
        <Route path="/runs" element={<RunsPage latestJobResult={jobResult} />} />
        <Route
          path="/runs/:runId"
          element={<RunsPage latestJobResult={jobResult} />}
        />
        <Route
          path="/runs/:runId/records/:recordId"
          element={<RunsPage latestJobResult={jobResult} />}
        />
        <Route
          path="/library"
          element={
            <PlaceholderPage
              eyebrow="Library"
              title="Shared recipes, assets, and brand kits"
              description="This shell location is reserved for reusable recipes, brand kits, subtitle presets, music presets, and prompt blocks."
            />
          }
        />
        <Route
          path="/admin"
          element={
            <PlaceholderPage
              eyebrow="Admin"
              title="Provider defaults and guardrails"
              description="Admin remains intentionally deferred so the creative and operational surfaces land first without widening backend scope."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ThemeProvider>
  );
}
