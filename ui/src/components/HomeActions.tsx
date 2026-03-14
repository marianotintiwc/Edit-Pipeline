interface HomeActionsProps {
  onCreateRun: () => void;
  onMonitorRun: () => void;
  onReviewRecord: () => void;
}

export function HomeActions({
  onCreateRun,
  onMonitorRun,
  onReviewRecord,
}: HomeActionsProps) {
  return (
    <section>
      <button type="button" onClick={onCreateRun}>
        Create a new run
      </button>
      <button type="button" onClick={onMonitorRun}>
        Monitor current run
      </button>
      <button type="button" onClick={onReviewRecord}>
        Review record
      </button>
    </section>
  );
}
