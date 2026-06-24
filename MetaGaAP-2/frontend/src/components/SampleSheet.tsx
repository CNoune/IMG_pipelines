// Sample sheet editor: add, remove and edit samples (reads, optional reverse
// reads, per-sample reference, and read-group metadata). Sample names must be
// unique within a run.
import type { ReadGroup, RunConfig, Sample } from "../types";
import FilePicker from "./FilePicker";
import { cls } from "../lib/format";

interface SampleSheetProps {
  /** Current run configuration (controlled). */
  config: RunConfig;
  /** Called with a fresh, immutably-updated configuration. */
  onChange: (next: RunConfig) => void;
}

/** Build a new RunConfig carrying a fresh samples array. */
function withSamples(config: RunConfig, samples: Sample[]): RunConfig {
  return { ...config, samples };
}

/** Default read-group metadata seeded from the sample name. */
function defaultReadGroup(sampleName: string): ReadGroup {
  return {
    sample: sampleName,
    library: "lib1",
    platform: "ILLUMINA",
    unit: "unit1",
  };
}

/** Create a blank sample with a name unique amongst the existing samples. */
function blankSample(existing: Sample[]): Sample {
  const base = "sample";
  let n = existing.length + 1;
  const taken = new Set(existing.map((s) => s.name));
  let name = `${base}${n}`;
  while (taken.has(name)) {
    n += 1;
    name = `${base}${n}`;
  }
  return {
    name,
    r1: "",
    r2: null,
    reference: null,
    read_group: defaultReadGroup(name),
  };
}

/**
 * A table-style editor for the run's samples. Each row exposes the sample name,
 * forward and optional reverse FASTQ pickers, a per-sample reference picker
 * (only in per-sample reference mode), and the four read-group fields. Duplicate
 * names are flagged inline.
 */
export default function SampleSheet({ config, onChange }: SampleSheetProps) {
  const samples = config.samples;
  const perSampleReference = config.reference_mode === "multiple";

  // Names that appear more than once (case-sensitive), for inline validation.
  const duplicates = new Set<string>();
  const seen = new Set<string>();
  for (const s of samples) {
    const key = s.name.trim();
    if (key && seen.has(key)) duplicates.add(key);
    seen.add(key);
  }

  const updateSample = (index: number, fields: Partial<Sample>) => {
    const next = samples.map((s, i) => (i === index ? { ...s, ...fields } : s));
    onChange(withSamples(config, next));
  };

  const updateReadGroup = (index: number, fields: Partial<ReadGroup>) => {
    const target = samples[index];
    const rg: ReadGroup = {
      ...(target.read_group ?? defaultReadGroup(target.name)),
      ...fields,
    };
    updateSample(index, { read_group: rg });
  };

  const addSample = () => {
    onChange(withSamples(config, [...samples, blankSample(samples)]));
  };

  const removeSample = (index: number) => {
    onChange(withSamples(config, samples.filter((_, i) => i !== index)));
  };

  return (
    <section className="flex flex-col gap-4" aria-label="Sample sheet">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          {samples.length} sample{samples.length === 1 ? "" : "s"}
        </p>
        <button
          type="button"
          onClick={addSample}
          className="rounded-md bg-sky-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1"
        >
          + Add sample
        </button>
      </div>

      {samples.length === 0 && (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          No samples yet. Add at least one sample to run the pipeline.
        </p>
      )}

      <ul className="flex flex-col gap-4">
        {samples.map((sample, index) => {
          const isDuplicate = duplicates.has(sample.name.trim());
          const nameFieldId = `sample-name-${index}`;
          return (
            <li
              key={index}
              className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <label
                    htmlFor={nameFieldId}
                    className="text-sm font-medium text-slate-700"
                  >
                    Sample name
                  </label>
                  <input
                    id={nameFieldId}
                    type="text"
                    value={sample.name}
                    spellCheck={false}
                    autoComplete="off"
                    aria-invalid={isDuplicate}
                    onChange={(e) =>
                      updateSample(index, { name: e.target.value })
                    }
                    className={cls(
                      "rounded-md border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-1",
                      isDuplicate
                        ? "border-rose-400 focus:border-rose-500 focus:ring-rose-500"
                        : "border-slate-300 focus:border-sky-500 focus:ring-sky-500",
                    )}
                  />
                  {isDuplicate && (
                    <p className="text-xs text-rose-600">
                      Duplicate name — sample names must be unique.
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => removeSample(index)}
                  aria-label={`Remove sample ${sample.name || index + 1}`}
                  className="mt-6 shrink-0 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-400"
                >
                  Remove
                </button>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FilePicker
                  label="Forward reads (R1)"
                  mode="file"
                  value={sample.r1}
                  onChange={(p) => updateSample(index, { r1: p })}
                />
                <FilePicker
                  label="Reverse reads (R2, optional)"
                  mode="file"
                  value={sample.r2 ?? ""}
                  onChange={(p) => updateSample(index, { r2: p || null })}
                />
              </div>

              {perSampleReference && (
                <FilePicker
                  label="Reference FASTA (this sample)"
                  mode="file"
                  value={sample.reference ?? ""}
                  onChange={(p) =>
                    updateSample(index, { reference: p || null })
                  }
                />
              )}

              <fieldset className="flex flex-col gap-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Read group
                </legend>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <ReadGroupField
                    label="Sample (RGSM)"
                    index={index}
                    field="sample"
                    value={sample.read_group?.sample ?? ""}
                    onChange={updateReadGroup}
                  />
                  <ReadGroupField
                    label="Library (RGLB)"
                    index={index}
                    field="library"
                    value={sample.read_group?.library ?? ""}
                    onChange={updateReadGroup}
                  />
                  <ReadGroupField
                    label="Platform (RGPL)"
                    index={index}
                    field="platform"
                    value={sample.read_group?.platform ?? ""}
                    onChange={updateReadGroup}
                  />
                  <ReadGroupField
                    label="Unit (RGPU)"
                    index={index}
                    field="unit"
                    value={sample.read_group?.unit ?? ""}
                    onChange={updateReadGroup}
                  />
                </div>
              </fieldset>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

interface ReadGroupFieldProps {
  label: string;
  index: number;
  field: keyof ReadGroup;
  value: string;
  onChange: (index: number, fields: Partial<ReadGroup>) => void;
}

/** A single labelled read-group text input. */
function ReadGroupField({
  label,
  index,
  field,
  value,
  onChange,
}: ReadGroupFieldProps) {
  const fieldId = `rg-${field}-${index}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={fieldId} className="text-xs font-medium text-slate-600">
        {label}
      </label>
      <input
        id={fieldId}
        type="text"
        value={value}
        spellCheck={false}
        autoComplete="off"
        onChange={(e) =>
          onChange(index, { [field]: e.target.value } as Partial<ReadGroup>)
        }
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
      />
    </div>
  );
}
