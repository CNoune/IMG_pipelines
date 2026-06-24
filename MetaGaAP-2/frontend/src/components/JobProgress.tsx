// Live job progress view: subscribes to a job's WebSocket event stream, mirrors
// stage status per sample, streams log lines into a scrollable panel, and offers
// a Cancel control. Calls onComplete once the job reaches a terminal state.
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  Job,
  JobState,
  SampleResult,
  StageName,
  StageResult,
  StageStatus,
  WSEvent,
} from "../types";
import { api, subscribeJob } from "../api";
import { cls, fmtPct } from "../lib/format";

interface JobProgressProps {
  jobId: string;
  /** Invoked once with the final job snapshot when it reaches a terminal state. */
  onComplete: (job: Job) => void;
}

/** Maximum number of log lines retained in the scrollback panel. */
const MAX_LOG_LINES = 500;

/** Ordered, human-friendly labels for the pipeline stages. */
const STAGE_LABELS: Record<StageName, string> = {
  trim: "Trim",
  align_call: "Align & call",
  haplotypes: "Haplotypes",
  confirm: "Confirm",
  merge: "Merge",
};

const TERMINAL_STATES: ReadonlySet<JobState> = new Set<JobState>([
  "completed",
  "failed",
  "cancelled",
]);

/** Tailwind classes describing the badge for a given stage status. */
function stageStatusClasses(status: StageStatus): string {
  switch (status) {
    case "running":
      return "border-sky-300 bg-sky-50 text-sky-700";
    case "done":
      return "border-emerald-300 bg-emerald-50 text-emerald-700";
    case "failed":
      return "border-rose-300 bg-rose-50 text-rose-700";
    case "skipped":
      return "border-slate-200 bg-slate-50 text-slate-400";
    default:
      return "border-slate-200 bg-white text-slate-400";
  }
}

/** Tailwind classes for the overall job-state pill. */
function jobStateClasses(state: JobState): string {
  switch (state) {
    case "running":
      return "border-sky-300 bg-sky-50 text-sky-700";
    case "completed":
      return "border-emerald-300 bg-emerald-50 text-emerald-700";
    case "failed":
      return "border-rose-300 bg-rose-50 text-rose-700";
    case "cancelled":
      return "border-amber-300 bg-amber-50 text-amber-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-500";
  }
}

/**
 * Replace (or insert) a stage result for a given sample, returning a new samples
 * array. Existing samples and stages are preserved; the matching stage is
 * overwritten by name, otherwise appended.
 */
function applyStageEvent(
  samples: SampleResult[],
  sampleName: string,
  stage: StageResult,
): SampleResult[] {
  let matched = false;
  const next = samples.map((s) => {
    if (s.sample !== sampleName) return s;
    matched = true;
    let replaced = false;
    const stages = s.stages.map((st) => {
      if (st.name === stage.name) {
        replaced = true;
        return stage;
      }
      return st;
    });
    if (!replaced) stages.push(stage);
    return { ...s, stages };
  });
  if (!matched) {
    next.push({
      sample: sampleName,
      stages: [stage],
      confirmed_fasta: null,
      stats_csv: null,
      counts_csv: null,
      n_confirmed: 0,
      n_haplotypes: 0,
    });
  }
  return next;
}

/**
 * Render live progress for a running (or recently finished) job. Seeds its
 * state from api.getJob, then updates from the WebSocket stream until the job
 * terminates. Logs are capped at the most recent MAX_LOG_LINES entries.
 */
export default function JobProgress({ jobId, onComplete }: JobProgressProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const logRef = useRef<HTMLDivElement>(null);
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Fire onComplete exactly once when a terminal job snapshot is observed.
  // The WebSocket stream carries per-stage updates but not the final per-sample
  // summary (n_haplotypes / n_confirmed / output paths), so the locally
  // reconstructed snapshot can be missing those. Re-fetch the authoritative job
  // before handing off to the results view; fall back to the local snapshot if
  // that request fails.
  const maybeComplete = useCallback((snapshot: Job) => {
    if (completedRef.current) return;
    if (TERMINAL_STATES.has(snapshot.state)) {
      completedRef.current = true;
      api
        .getJob(snapshot.id)
        .then((fresh) => onCompleteRef.current(fresh))
        .catch(() => onCompleteRef.current(snapshot));
    }
  }, []);

  // Seed initial state from the REST snapshot.
  useEffect(() => {
    let active = true;
    completedRef.current = false;
    setSeedError(null);
    api
      .getJob(jobId)
      .then((snapshot) => {
        if (!active) return;
        setJob(snapshot);
        maybeComplete(snapshot);
      })
      .catch((err) => {
        if (!active) return;
        setSeedError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      active = false;
    };
  }, [jobId, maybeComplete]);

  // Subscribe to the live event stream.
  useEffect(() => {
    const unsubscribe = subscribeJob(
      jobId,
      (ev: WSEvent) => {
        if (ev.type === "log") {
          if (ev.line != null) {
            setLogs((prev) => {
              const next = prev.concat(ev.line as string);
              return next.length > MAX_LOG_LINES
                ? next.slice(next.length - MAX_LOG_LINES)
                : next;
            });
          }
          return;
        }
        setJob((prev) => {
          if (!prev) return prev;
          let next = prev;
          if (ev.type === "stage" && ev.sample && ev.stage) {
            next = {
              ...next,
              samples: applyStageEvent(next.samples, ev.sample, ev.stage),
              current_stage: ev.stage.name,
            };
          }
          if (ev.type === "state" || ev.type === "done") {
            next = {
              ...next,
              state: ev.state ?? next.state,
              progress: ev.progress ?? next.progress,
            };
          } else if (ev.progress != null) {
            next = { ...next, progress: ev.progress };
          }
          maybeComplete(next);
          return next;
        });
      },
      (open) => setConnected(open),
    );
    return () => {
      unsubscribe();
    };
  }, [jobId, maybeComplete]);

  // Keep the log panel scrolled to the newest line.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      const updated = await api.cancelJob(jobId);
      setJob(updated);
      maybeComplete(updated);
    } catch (err) {
      setLogs((prev) =>
        prev.concat(
          `[client] Cancel failed: ${err instanceof Error ? err.message : String(err)}`,
        ),
      );
    } finally {
      setCancelling(false);
    }
  }, [jobId, maybeComplete]);

  if (seedError && !job) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700"
      >
        Could not load job: {seedError}
      </div>
    );
  }

  if (!job) {
    return (
      <div
        className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500"
        aria-busy="true"
      >
        Loading job…
      </div>
    );
  }

  const isTerminal = TERMINAL_STATES.has(job.state);
  const progress = Math.min(1, Math.max(0, job.progress));

  return (
    <section className="flex flex-col gap-4" aria-label="Job progress">
      {/* Header: state pill, connection indicator, cancel. */}
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={cls(
            "rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide",
            jobStateClasses(job.state),
          )}
        >
          {job.state}
        </span>

        <span
          className="flex items-center gap-1.5 text-xs text-slate-500"
          title={connected ? "Live connection active" : "Reconnecting…"}
        >
          <span
            aria-hidden="true"
            className={cls(
              "inline-block h-2.5 w-2.5 rounded-full",
              connected ? "bg-emerald-500" : "bg-slate-300",
              !connected && !isTerminal && "animate-pulse",
            )}
          />
          {connected ? "Live" : isTerminal ? "Closed" : "Reconnecting…"}
        </span>

        {job.current_stage && !isTerminal && (
          <span className="text-xs text-slate-500">
            Current stage:{" "}
            <span className="font-medium text-slate-700">
              {STAGE_LABELS[job.current_stage]}
            </span>
          </span>
        )}

        <div className="ml-auto">
          <button
            type="button"
            onClick={() => void handleCancel()}
            disabled={isTerminal || cancelling}
            className="rounded-md border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 focus:outline-none focus:ring-1 focus:ring-rose-500 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400 disabled:hover:bg-white"
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        </div>
      </div>

      {/* Overall progress bar. */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Overall progress</span>
          <span className="font-medium text-slate-700">{fmtPct(progress)}</span>
        </div>
        <div
          className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          aria-label="Overall job progress"
        >
          <div
            className={cls(
              "h-full rounded-full transition-all duration-300",
              job.state === "failed"
                ? "bg-rose-500"
                : job.state === "cancelled"
                  ? "bg-amber-500"
                  : "bg-sky-500",
            )}
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>

      {job.error && (
        <div
          role="alert"
          className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          {job.error}
        </div>
      )}

      {/* Per-sample stage list. */}
      <ul className="flex flex-col gap-3">
        {job.samples.map((sample) => (
          <li
            key={sample.sample}
            className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
          >
            <div className="mb-2 text-sm font-semibold text-slate-800">
              {sample.sample}
            </div>
            <ul className="flex flex-wrap gap-2">
              {sample.stages.map((stage) => (
                <li
                  key={stage.name}
                  className={cls(
                    "flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium",
                    stageStatusClasses(stage.status),
                  )}
                  title={stage.message ?? undefined}
                >
                  <span>{STAGE_LABELS[stage.name]}</span>
                  <span className="opacity-70">·</span>
                  <span className="capitalize">{stage.status}</span>
                </li>
              ))}
              {sample.stages.length === 0 && (
                <li className="text-xs text-slate-400">Waiting to start…</li>
              )}
            </ul>
          </li>
        ))}
        {job.samples.length === 0 && (
          <li className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-400">
            No samples in this job.
          </li>
        )}
      </ul>

      {/* Log scrollback. */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Log output</span>
          <span>{logs.length} line{logs.length === 1 ? "" : "s"}</span>
        </div>
        <div
          ref={logRef}
          role="log"
          aria-live="polite"
          aria-label="Job log output"
          className="h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100"
        >
          {logs.length === 0 ? (
            <div className="text-slate-500">No log output yet…</div>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-words">
                {line}
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
