import type { BatchDetail } from "../types";

interface BatchProgressProps {
  batch: BatchDetail;
}

export function BatchProgress({ batch }: BatchProgressProps) {
  const submittedRows = batch.submitted_rows ?? 0;

  return (
    <section>
      <h3>Submission progress</h3>
      <p>
        {submittedRows} row{submittedRows === 1 ? "" : "s"} submitted
      </p>
      {batch.rows.map((row) => (
        <article key={`${row.row_number}-${row.run_id ?? row.job_id ?? row.status}`}>
          <p>Row {row.row_number}</p>
          <p>Status: {row.status}</p>
          {row.run_id ? <p>{row.run_id}</p> : null}
          {row.job_id ? <p>{row.job_id}</p> : null}
        </article>
      ))}
    </section>
  );
}
