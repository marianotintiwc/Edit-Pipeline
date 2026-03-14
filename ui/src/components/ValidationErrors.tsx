interface ValidationErrorsProps {
  errors: string[];
}

export function ValidationErrors({ errors }: ValidationErrorsProps) {
  if (errors.length === 0) {
    return null;
  }

  return (
    <section aria-label="Validation errors">
      {/* Researched Stripe/CSVBox 2026 → user-facing heading reduces anxiety vs generic "Errors" */}
      <h2>Something went wrong</h2>
      <ul>
        {errors.map((error) => (
          <li key={error}>{error}</li>
        ))}
      </ul>
    </section>
  );
}
