import type { Recipe } from "../data/recipes";
import { CURATED_RECIPES } from "../data/recipes";
import { Button, SurfaceCard } from "./primitives";

interface RecipeCardsProps {
  onSelect: (recipe: Recipe) => void;
}

export function RecipeCards({ onSelect }: RecipeCardsProps) {
  return (
    <section className="home-grid home-grid--cards">
      {CURATED_RECIPES.map((recipe) => (
        <SurfaceCard key={recipe.id}>
          <span className="section-header">Recipe</span>
          <h3>{recipe.label}</h3>
          <p className="helper">{recipe.description}</p>
          <div className="button-row">
            <Button onClick={() => onSelect(recipe)}>Use {recipe.label}</Button>
          </div>
        </SurfaceCard>
      ))}
    </section>
  );
}
