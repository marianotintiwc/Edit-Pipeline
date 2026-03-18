import { useEffect, useState } from "react";
import { CURATED_RECIPES } from "../../data/recipes";
import type { Recipe } from "../../data/recipes";
import type { Profile } from "../../types";
import { listProfiles } from "../../api";
import { Button, SurfaceCard } from "../primitives";

export type RecipeOrProfile = { kind: "recipe"; recipe: Recipe } | { kind: "profile"; profile: Profile };

interface BatchRecipeProps {
  selectedId: string | null;
  onSelect: (item: RecipeOrProfile | null) => void;
}

function toInput(item: RecipeOrProfile | null): Record<string, unknown> | null {
  if (!item) return null;
  if (item.kind === "recipe") return (item.recipe.input ?? null) as Record<string, unknown> | null;
  return (item.profile.input ?? null) as Record<string, unknown> | null;
}

export function BatchRecipe({ selectedId, onSelect }: BatchRecipeProps) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    void listProfiles()
      .then((res) => setProfiles(res.items))
      .catch(() => setProfiles([]))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <SurfaceCard>
      <span className="section-header">Recipe & profile assignment</span>
      <h3>Choose default recipe or profile for rows</h3>
      <p className="helper">
        Selected recipe/profile will be merged with CSV row data on upload and submit.
      </p>
      <div className="surface-stack">
        <div className="button-row">
          <Button variant={selectedId === null ? "secondary" : "ghost"} onClick={() => onSelect(null)}>
            None
          </Button>
        </div>
        {CURATED_RECIPES.map((recipe) => (
          <div key={`recipe-${recipe.id}`} className="button-row">
            <span>{recipe.label}</span>
            <Button
              variant={selectedId === `recipe-${recipe.id}` ? "secondary" : "ghost"}
              onClick={() => onSelect({ kind: "recipe", recipe })}
            >
              {selectedId === `recipe-${recipe.id}` ? "Selected" : "Select"}
            </Button>
          </div>
        ))}
        {isLoading ? (
          <p className="helper">Loading profiles…</p>
        ) : (
          profiles.map((profile) => (
            <div key={`profile-${profile.profile_id}`} className="button-row">
              <span>
                {profile.name}
                {profile.is_meli ? " (MELI)" : ""}
              </span>
              <Button
                variant={selectedId === `profile-${profile.profile_id}` ? "secondary" : "ghost"}
                onClick={() => onSelect({ kind: "profile", profile })}
              >
                {selectedId === `profile-${profile.profile_id}` ? "Selected" : "Select"}
              </Button>
            </div>
          ))
        )}
      </div>
    </SurfaceCard>
  );
}

export { toInput as batchRecipeToInput };
