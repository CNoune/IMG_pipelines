// MetaGaAP 2 single-page run wizard. Owns the RunConfig being assembled and the
// active Job, walks the user through Engine -> Samples -> Parameters -> Run ->
// Results, and talks to the backend via the REST/WebSocket client in ./api.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Job, RunConfig, ServerInfo } from "./types";
import { api } from "./api";
import { cls } from "./lib/format";
import Stepper from "./components/Stepper";
import EngineStatus from "./components/EngineStatus";
import RunConfigForm from "./components/RunConfigForm";
import SampleSheet from "./components/SampleSheet";
import ParamsPanel from "./components/ParamsPanel";
import JobProgress from "./components/JobProgress";
import ResultsView from "./components/ResultsView";

const STEPS = ["Engine", "Samples", "Parameters", "Run", "Results"] as const;

/** Build a fresh RunConfig whose defaults mirror backend/metagaap2/models.py. */
function defaultConfig(): RunConfig {
  return {
    run_name: "run1",
    work_dir: "",
    engine: "portable",
    aligner: "builtin",
    threads: 4,
    reference_mode: "single",
    reference: null,
    merge_single_reference: true,
    samples: [],
    qc: {
      enabled: true,
      min_quality: 20,
      min_length: 30,
      trim_front: 0,
      trim_tail: 0,
      adapter_fwd: null,
      adapter_rev: null,
      detect_adapters: true,
    },
    variants: {
      caller: "builtin",
      min_base_quality: 20,
      min_mapping_quality: 20,
      min_depth: 10,
      min_alt_fraction: 0.02,
      ploidy: 2,
    },
    haplotypes: {
      window: null,
      max_haplotypes_per_window: 1024,
      max_variants_per_window: 12,
      step: null,
    },
    confirm: {
      min_mapped_reads: 2,
      min_identity: 0.9,
    },
  };
}

export default function App() {
  const [step, setStep] = useState(0);
  const [config, setConfig] = useState<RunConfig>(defaultConfig);
  const [info, setInfo] = useState<ServerInfo | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch the server's engine/tool report once on mount and align the config's
  // engine selection with the server's recommended default.
  useEffect(() => {
    let cancelled = false;
    void api
      .serverInfo()
      .then((result) => {
        if (cancelled) return;
        setInfo(result);
        setConfig((prev) => ({ ...prev, engine: result.default_engine }));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Submitting the run requires at least one sample, a destination directory and
  // (for single-reference mode) a shared reference.
  const canSubmit = useMemo(() => {
    if (!config.run_name.trim() || !config.work_dir.trim()) return false;
    if (config.samples.length === 0) return false;
    if (config.reference_mode === "single" && !config.reference?.trim()) {
      return false;
    }
    return true;
  }, [config]);

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createJob(config);
      setJob(created);
      setStep(3); // Run
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }, [config]);

  const handleJobComplete = useCallback((finished: Job) => {
    setJob(finished);
    setStep(4); // Results
  }, []);

  const startOver = useCallback(() => {
    setJob(null);
    setConfig((prev) => ({ ...defaultConfig(), engine: prev.engine }));
    setError(null);
    setStep(0);
  }, []);

  const goNext = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-col gap-0.5 px-4 py-5 sm:px-6">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            MetaGaAP 2
          </h1>
          <p className="text-sm text-slate-500">
            Cross-platform quasispecies and meta-barcode pipeline
          </p>
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6">
        <Stepper steps={[...STEPS]} current={step} />

        {error && (
          <div
            role="alert"
            className="flex items-start justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="shrink-0 font-medium text-rose-600 hover:text-rose-800"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          {step === 0 && (
            <div className="flex flex-col gap-6">
              <EngineStatus info={info} />
              <RunConfigForm config={config} onChange={setConfig} info={info} />
            </div>
          )}
          {step === 1 && (
            <SampleSheet config={config} onChange={setConfig} />
          )}
          {step === 2 && (
            <ParamsPanel config={config} onChange={setConfig} info={info} />
          )}
          {step === 3 && (
            job ? (
              <JobProgress jobId={job.id} onComplete={handleJobComplete} />
            ) : (
              <p className="text-sm text-slate-500">
                No run has been started yet. Return to the previous steps and
                submit a run.
              </p>
            )
          )}
          {step === 4 && (
            job ? (
              <ResultsView job={job} />
            ) : (
              <p className="text-sm text-slate-500">No results to display.</p>
            )
          )}
        </div>

        {/* Wizard navigation. The Run and Results steps manage their own flow. */}
        <nav
          className="flex items-center justify-between gap-3"
          aria-label="Wizard navigation"
        >
          <button
            type="button"
            onClick={goBack}
            disabled={step === 0 || step === 3}
            className={cls(
              "rounded-md border px-4 py-2 text-sm font-medium transition-colors",
              step === 0 || step === 3
                ? "cursor-not-allowed border-slate-200 text-slate-300"
                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100",
            )}
          >
            Back
          </button>

          <div className="flex items-center gap-3">
            {step === 2 && (
              <button
                type="button"
                onClick={() => void handleSubmit()}
                disabled={!canSubmit || submitting}
                className={cls(
                  "rounded-md px-5 py-2 text-sm font-semibold text-white transition-colors",
                  !canSubmit || submitting
                    ? "cursor-not-allowed bg-slate-300"
                    : "bg-sky-600 hover:bg-sky-700",
                )}
              >
                {submitting ? "Starting…" : "Start run"}
              </button>
            )}
            {step < 2 && (
              <button
                type="button"
                onClick={goNext}
                className="rounded-md bg-sky-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-700"
              >
                Next
              </button>
            )}
            {step === 4 && (
              <button
                type="button"
                onClick={startOver}
                className="rounded-md bg-sky-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-700"
              >
                New run
              </button>
            )}
          </div>
        </nav>
      </main>
    </div>
  );
}
