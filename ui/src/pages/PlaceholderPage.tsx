import { EmptyState, SurfaceCard } from "../components/primitives";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
}

export function PlaceholderPage({ eyebrow, title, description }: PlaceholderPageProps) {
  return (
    <div className="shell-page">
      <SurfaceCard>
        <span className="micro-label">{eyebrow}</span>
        <h2>{title}</h2>
        <EmptyState title="Planned for the next phase" description={description} />
      </SurfaceCard>
    </div>
  );
}
