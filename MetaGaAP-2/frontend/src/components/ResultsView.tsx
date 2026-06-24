// Results view for a finished job: per-sample cards with haplotype/confirmed
// counts and download links, plus a cross-sample summary table. Renders a
// friendly empty state when nothing was produced.
import type { Job, SampleResult } from "../types";
import { api } from "../api";
import { cls, fmtInt } from "../lib/format";

interface ResultsViewProps {
  job: Job;
}

interface DownloadSpec {
  label: string;
  path: string;
}

/** Collect the available download links for a sample, skipping missing outputs. */
function downloadsFor(sample: SampleResult): DownloadSpec[] {
  const specs: DownloadSpec[] = [];
  if (sample.confirmed_fasta) {
    specs.push({ label: "Confirmed FASTA", path: sample.confirmed_fasta });
  }
  if (sample.stats_csv) {
    specs.push({ label: "Stats CSV", path: sample.stats_csv });
  }
  if (sample.counts_csv) {
    specs.push({ label: "Counts CSV", path: sample.counts_csv });
  }
  return specs;
}

/**
 * Render the results for a completed (or terminal) job. Each sample is shown as
 * a card summarising haplotype and confirmed counts with download links for any
 * generated artefacts. A summary table aggregates counts across all samples.
 */
export default function ResultsView({ job }: ResultsViewProps) {
  const samples = job.samples;
  const anyOutputs = samples.some((s) => downloadsFor(s).length > 0);
  const hasResults = samples.length > 0 && (anyOutputs || job.state === "completed");

  if (!hasResults) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
        <span className="text-3xl" aria-hidden="true">
          📭
        </span>
        <p className="text-sm font-medium text-slate-700">No results to show</p>
        <p className="max-w-md text-xs text-slate-500">
          {job.state === "failed"
            ? "This run finished with errors, so no confirmed sequences were produced. Check the job log for details."
            : job.state === "cancelled"
              ? "This run was cancelled before any results were produced."
              : "Once the pipeline completes, confirmed sequences and statistics will appear here."}
        </p>
      </div>
    );
  }

  const totalHaplotypes = samples.reduce((sum, s) => sum + s.n_haplotypes, 0);
  const totalConfirmed = samples.reduce((sum, s) => sum + s.n_confirmed, 0);

  return (
    <section className="flex flex-col gap-6" aria-label="Job results">
      {/* Per-sample cards. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {samples.map((sample) => {
          const downloads = downloadsFor(sample);
          return (
            <article
              key={sample.sample}
              className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <h3 className="truncate text-sm font-semibold text-slate-800" title={sample.sample}>
                {sample.sample}
              </h3>

              <dl className="grid grid-cols-2 gap-2">
                <div className="rounded-md bg-slate-50 px-3 py-2">
                  <dt className="text-xs text-slate-500">Haplotypes</dt>
                  <dd className="text-lg font-semibold text-slate-800">
                    {fmtInt(sample.n_haplotypes)}
                  </dd>
                </div>
                <div className="rounded-md bg-emerald-50 px-3 py-2">
                  <dt className="text-xs text-emerald-700">Confirmed</dt>
                  <dd className="text-lg font-semibold text-emerald-700">
                    {fmtInt(sample.n_confirmed)}
                  </dd>
                </div>
              </dl>

              {downloads.length > 0 ? (
                <ul className="flex flex-col gap-1.5">
                  {downloads.map((dl) => (
                    <li key={dl.path}>
                      <a
                        href={api.downloadUrl(job.id, dl.path)}
                        download
                        className="flex items-center gap-1.5 rounded-md border border-sky-200 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-700 hover:bg-sky-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
                      >
                        <span aria-hidden="true">⬇</span>
                        <span className="min-w-0 flex-1 truncate">{dl.label}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-400">No downloadable outputs.</p>
              )}
            </article>
          );
        })}
      </div>

      {/* Cross-sample summary table. */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Cross-sample results summary</caption>
          <thead>
            <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-4 py-2 font-semibold">
                Sample
              </th>
              <th scope="col" className="px-4 py-2 text-right font-semibold">
                Haplotypes
              </th>
              <th scope="col" className="px-4 py-2 text-right font-semibold">
                Confirmed
              </th>
              <th scope="col" className="px-4 py-2 text-right font-semibold">
                Downloads
              </th>
            </tr>
          </thead>
          <tbody>
            {samples.map((sample, i) => (
              <tr
                key={sample.sample}
                className={cls(
                  "border-t border-slate-200",
                  i % 2 === 1 && "bg-slate-50/50",
                )}
              >
                <th
                  scope="row"
                  className="max-w-xs truncate px-4 py-2 text-left font-medium text-slate-800"
                  title={sample.sample}
                >
                  {sample.sample}
                </th>
                <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                  {fmtInt(sample.n_haplotypes)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                  {fmtInt(sample.n_confirmed)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-500">
                  {fmtInt(downloadsFor(sample).length)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
              <th scope="row" className="px-4 py-2 text-left text-slate-800">
                Total ({fmtInt(samples.length)})
              </th>
              <td className="px-4 py-2 text-right tabular-nums text-slate-800">
                {fmtInt(totalHaplotypes)}
              </td>
              <td className="px-4 py-2 text-right tabular-nums text-emerald-700">
                {fmtInt(totalConfirmed)}
              </td>
              <td className="px-4 py-2" />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
