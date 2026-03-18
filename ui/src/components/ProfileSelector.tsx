import { useEffect, useState } from "react";
import type { JobInput, Profile } from "../types";
import { Button, SurfaceCard } from "./primitives";
import { listProfiles } from "../api";

interface ProfileSelectorProps {
  selectedProfileId: string | null;
  onSelectProfile: (profile: Profile | null) => void;
  appliedProfileId?: string | null;
}

function deepMerge(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const result = { ...base };
  for (const key of Object.keys(patch)) {
    const patchVal = patch[key];
    if (
      patchVal !== null &&
      typeof patchVal === "object" &&
      !Array.isArray(patchVal) &&
      result[key] !== null &&
      typeof result[key] === "object" &&
      !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(
        result[key] as Record<string, unknown>,
        patchVal as Record<string, unknown>,
      );
    } else {
      result[key] = patchVal;
    }
  }
  return result;
}

export function applyProfileToForm(form: JobInput, profile: Profile): JobInput {
  const input = profile.input ?? {};
  const merged = deepMerge(
    form as unknown as Record<string, unknown>,
    input as Record<string, unknown>,
  );
  return {
    ...form,
    ...merged,
    clips: (merged.clips as JobInput["clips"]) ?? form.clips,
  } as JobInput;
}

export function ProfileSelector({
  selectedProfileId,
  onSelectProfile,
  appliedProfileId,
}: ProfileSelectorProps) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    void listProfiles()
      .then((res) => setProfiles(res.items))
      .catch(() => setProfiles([]))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <SurfaceCard muted>
        <span className="section-header">Profile</span>
        <p className="helper">Loading profiles…</p>
      </SurfaceCard>
    );
  }

  return (
    <SurfaceCard>
      <span className="section-header">Profile</span>
      <h3>Apply a profile (MELI or custom)</h3>
      <p className="helper">
        Profiles apply defaults over your form. You can still edit values after applying.
      </p>
      <div className="surface-stack">
        <div className="button-row">
          <Button
            variant={selectedProfileId === null ? "secondary" : "ghost"}
            onClick={() => onSelectProfile(null)}
          >
            None
          </Button>
        </div>
        {profiles.map((profile) => (
          <div key={profile.profile_id} className="button-row">
            <span>
              {profile.name}
              {profile.is_meli ? " (MELI)" : ""}
            </span>
            <Button
              variant={selectedProfileId === profile.profile_id ? "secondary" : "ghost"}
              onClick={() => onSelectProfile(profile)}
            >
              {selectedProfileId === profile.profile_id ? "Selected" : "Select"}
            </Button>
          </div>
        ))}
      </div>
      {appliedProfileId ? (
        <p className="helper" style={{ marginTop: "var(--space-2)" }}>
          Profile applied. You can still edit values.
        </p>
      ) : null}
    </SurfaceCard>
  );
}
