// Global run settings: run name, work dir, engine/aligner, threads, reference.
// Engine and aligner choices are constrained by the detected server capabilities.
import type {
  Aligner,
  EngineKey,
  ReferenceMode,
  RunConfig,
  ServerInfo,
} from "../types";
import FilePicker from "./FilePicker";

interface RunConfigFormProps {
  /** Current run configuration (controlled). */
  config: RunConfig;
  /** Called with a fresh, immutably-updated configuration. */
  onChange: (next: RunConfig) => void;
  /** Detected server capabilities (engines, tools, defaults). */
  info: ServerInfo | null;
}

/**
 * Produce a new RunConfig with the given top-level fields overridden. Always
 * returns a fresh object so React sees a changed reference.
 */
function patch(config: RunConfig, fields: Partial<RunConfig>): RunConfig {
  return { ...config, ...fields };
}

/**
 * Editor for the run-wide settings. Engine selection is limited to the engines
 * the server reports, the aligner list follows the chosen engine's supported
 * aligners, and changing engine resets the aligner to that engine's first
 * supported value to avoid an invalid combination.
 */
export default function RunConfigForm({
  config,
  onChange,
  info,
}: RunConfigFormProps) {
  const engines = info?.engines ?? [];
  const currentEngine = engines.find((e) => e.key === config.engine);
  const alignerOptions: Aligner[] = currentEngine?.aligners ?? [config.aligner];

  const handleEngineChange = (engine: EngineKey) => {
    const target = engines.find((e) => e.key === engine);
    // Reset aligner to the new engine's first supported aligner so the pair
    // stays valid; fall back to the existing aligner if nothing is reported.
    const nextAligner: Aligner = target?.aligners[0] ?? config.aligner;
    onChange(patch(config, { engine, aligner: nextAligner }));
  };

  const handleReferenceModeChange = (mode: ReferenceMode) => {
    // When switching away from single-reference, the run-level reference no
    // longer applies; clear it so it cannot silently linger.
    onChange(
      patch(config, {
        reference_mode: mode,
        reference: mode === "single" ? config.reference : null,
      }),
    );
  };

  return (
    <section className="flex flex-col gap-5" aria-label="Run configuration">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="run-name"
            className="text-sm font-medium text-slate-700"
          >
            Run name
          </label>
          <input
            id="run-name"
            type="text"
            value={config.run_name}
            spellCheck={false}
            autoComplete="off"
            placeholder="e.g. hcv_run_24062026"
            onChange={(e) => onChange(patch(config, { run_name: e.target.value }))}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
          <p className="text-xs text-slate-500">
            Labels the output directory under the working directory.
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="run-threads"
            className="text-sm font-medium text-slate-700"
          >
            Threads
          </label>
          <input
            id="run-threads"
            type="number"
            min={1}
            value={config.threads}
            onChange={(e) =>
              onChange(
                patch(config, {
                  threads: Math.max(1, Math.trunc(Number(e.target.value) || 1)),
                }),
              )
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
          <p className="text-xs text-slate-500">
            Worker threads per tool (minimum 1).
          </p>
        </div>
      </div>

      <FilePicker
        label="Working directory"
        mode="dir"
        value={config.work_dir}
        onChange={(p) => onChange(patch(config, { work_dir: p }))}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="run-engine"
            className="text-sm font-medium text-slate-700"
          >
            Engine
          </label>
          <select
            id="run-engine"
            value={config.engine}
            onChange={(e) => handleEngineChange(e.target.value as EngineKey)}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            {engines.length === 0 && (
              <option value={config.engine}>{config.engine}</option>
            )}
            {engines.map((e) => (
              <option key={e.key} value={e.key} disabled={!e.available}>
                {e.label}
                {e.available ? "" : " (unavailable)"}
              </option>
            ))}
          </select>
          {currentEngine?.note && (
            <p className="text-xs text-slate-500">{currentEngine.note}</p>
          )}
          {currentEngine && currentEngine.missing.length > 0 && (
            <p className="text-xs text-amber-600">
              Missing tools: {currentEngine.missing.join(", ")}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="run-aligner"
            className="text-sm font-medium text-slate-700"
          >
            Aligner
          </label>
          <select
            id="run-aligner"
            value={config.aligner}
            onChange={(e) =>
              onChange(patch(config, { aligner: e.target.value as Aligner }))
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            {alignerOptions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-500">
            Read aligner supported by the chosen engine.
          </p>
        </div>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium text-slate-700">
          Reference mode
        </legend>
        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-800">
            <input
              type="radio"
              name="reference-mode"
              value="single"
              checked={config.reference_mode === "single"}
              onChange={() => handleReferenceModeChange("single")}
              className="h-4 w-4 border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Single shared reference
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-800">
            <input
              type="radio"
              name="reference-mode"
              value="multiple"
              checked={config.reference_mode === "multiple"}
              onChange={() => handleReferenceModeChange("multiple")}
              className="h-4 w-4 border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Per-sample reference
          </label>
        </div>
        <p className="text-xs text-slate-500">
          Single mode maps every sample to one reference; per-sample mode reads
          a reference from each row of the sample sheet.
        </p>
      </fieldset>

      {config.reference_mode === "single" && (
        <div className="flex flex-col gap-3">
          <FilePicker
            label="Reference FASTA"
            mode="file"
            value={config.reference ?? ""}
            onChange={(p) => onChange(patch(config, { reference: p || null }))}
          />
          <label className="flex items-center gap-2 text-sm text-slate-800">
            <input
              type="checkbox"
              checked={config.merge_single_reference}
              onChange={(e) =>
                onChange(
                  patch(config, { merge_single_reference: e.target.checked }),
                )
              }
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Merge per-sample databases across samples
          </label>
          <p className="-mt-1 text-xs text-slate-500">
            Combines confirmed haplotypes from all samples into one merged
            database for the single-reference run.
          </p>
        </div>
      )}
    </section>
  );
}
