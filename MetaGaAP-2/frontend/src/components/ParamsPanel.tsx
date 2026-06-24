// Grouped parameter editor: QC/trimming, variant calling, haplotype database
// construction and confirmation. Numeric bounds mirror the pydantic Field
// constraints in backend/metagaap2/models.py.
import type { ReactNode } from "react";
import type {
  ConfirmParams,
  HaplotypeParams,
  QCParams,
  RunConfig,
  ServerInfo,
  VariantCaller,
  VariantParams,
} from "../types";

interface ParamsPanelProps {
  /** Current run configuration (controlled). */
  config: RunConfig;
  /** Called with a fresh, immutably-updated configuration. */
  onChange: (next: RunConfig) => void;
  /** Detected server capabilities; constrains the variant-caller list. */
  info: ServerInfo | null;
}

/** Return a new RunConfig with one sub-section object replaced immutably. */
function patchSection<K extends keyof RunConfig>(
  config: RunConfig,
  key: K,
  value: RunConfig[K],
): RunConfig {
  return { ...config, [key]: value };
}

/**
 * Editor for the four parameter groups. Every numeric field carries the same
 * min/max bounds the backend enforces, plus short help text. The variant caller
 * select is limited to the callers the chosen engine supports.
 */
export default function ParamsPanel({
  config,
  onChange,
  info,
}: ParamsPanelProps) {
  const { qc, variants, haplotypes, confirm } = config;

  const engine = info?.engines.find((e) => e.key === config.engine);
  const callerOptions: VariantCaller[] = engine?.callers ?? [variants.caller];

  const setQC = (fields: Partial<QCParams>) =>
    onChange(patchSection(config, "qc", { ...qc, ...fields }));
  const setVariants = (fields: Partial<VariantParams>) =>
    onChange(patchSection(config, "variants", { ...variants, ...fields }));
  const setHaplotypes = (fields: Partial<HaplotypeParams>) =>
    onChange(patchSection(config, "haplotypes", { ...haplotypes, ...fields }));
  const setConfirm = (fields: Partial<ConfirmParams>) =>
    onChange(patchSection(config, "confirm", { ...confirm, ...fields }));

  return (
    <div className="flex flex-col gap-6" aria-label="Pipeline parameters">
      {/* ----------------------------------------------------------------- */}
      {/* Quality control / trimming                                        */}
      {/* ----------------------------------------------------------------- */}
      <Group title="Quality control / trimming">
        <label className="flex items-center gap-2 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={qc.enabled}
            onChange={(e) => setQC({ enabled: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          Enable trimming
        </label>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField
            id="qc-min-quality"
            label="Min quality (Q)"
            help="Quality trim threshold (0–60)."
            value={qc.min_quality}
            min={0}
            max={60}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ min_quality: v })}
          />
          <NumberField
            id="qc-min-length"
            label="Min length"
            help="Discard reads shorter than this after trimming (≥1)."
            value={qc.min_length}
            min={1}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ min_length: v })}
          />
          <NumberField
            id="qc-trim-front"
            label="Trim front (5′)"
            help="Fixed bases cut from the 5′ end (≥0)."
            value={qc.trim_front}
            min={0}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ trim_front: v })}
          />
          <NumberField
            id="qc-trim-tail"
            label="Trim tail (3′)"
            help="Fixed bases cut from the 3′ end (≥0)."
            value={qc.trim_tail}
            min={0}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ trim_tail: v })}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField
            id="qc-adapter-fwd"
            label="Adapter (R1)"
            help="Optional 3′ adapter sequence for forward reads."
            value={qc.adapter_fwd ?? ""}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ adapter_fwd: v || null })}
          />
          <TextField
            id="qc-adapter-rev"
            label="Adapter (R2)"
            help="Optional 3′ adapter sequence for reverse reads."
            value={qc.adapter_rev ?? ""}
            disabled={!qc.enabled}
            onValue={(v) => setQC({ adapter_rev: v || null })}
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={qc.detect_adapters}
            disabled={!qc.enabled}
            onChange={(e) => setQC({ detect_adapters: e.target.checked })}
            className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:opacity-50"
          />
          Auto-detect adapters where supported
        </label>
      </Group>

      {/* ----------------------------------------------------------------- */}
      {/* Variant calling                                                   */}
      {/* ----------------------------------------------------------------- */}
      <Group title="Variant calling">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="var-caller"
            className="text-sm font-medium text-slate-700"
          >
            Caller
          </label>
          <select
            id="var-caller"
            value={variants.caller}
            onChange={(e) =>
              setVariants({ caller: e.target.value as VariantCaller })
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          >
            {callerOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-500">
            Variant caller supported by the chosen engine.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField
            id="var-min-base-quality"
            label="Min base quality"
            help="Minimum base quality (0–60)."
            value={variants.min_base_quality}
            min={0}
            max={60}
            onValue={(v) => setVariants({ min_base_quality: v })}
          />
          <NumberField
            id="var-min-mapping-quality"
            label="Min mapping quality"
            help="Minimum mapping quality (0–60)."
            value={variants.min_mapping_quality}
            min={0}
            max={60}
            onValue={(v) => setVariants({ min_mapping_quality: v })}
          />
          <NumberField
            id="var-min-depth"
            label="Min depth"
            help="Minimum site depth to consider a variant (≥1)."
            value={variants.min_depth}
            min={1}
            onValue={(v) => setVariants({ min_depth: v })}
          />
          <NumberField
            id="var-min-alt-fraction"
            label="Min ALT fraction"
            help="Minimum ALT allele fraction, 0–1 (quasispecies-sensitive)."
            value={variants.min_alt_fraction}
            min={0}
            max={1}
            step={0.01}
            float
            onValue={(v) => setVariants({ min_alt_fraction: v })}
          />
          <NumberField
            id="var-ploidy"
            label="Ploidy"
            help="Ploidy for bcftools call; ignored by the frequency caller (≥1)."
            value={variants.ploidy}
            min={1}
            onValue={(v) => setVariants({ ploidy: v })}
          />
        </div>
      </Group>

      {/* ----------------------------------------------------------------- */}
      {/* Haplotype database                                                */}
      {/* ----------------------------------------------------------------- */}
      <Group title="Haplotype database">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField
            id="hap-window"
            label="Window (bp)"
            help="Sliding-window size; blank = modal read length (≥1)."
            value={haplotypes.window}
            min={1}
            nullable
            onNullable={(v) => setHaplotypes({ window: v })}
          />
          <NumberField
            id="hap-step"
            label="Step (bp)"
            help="Window step; blank = window size, i.e. non-overlapping (≥1)."
            value={haplotypes.step}
            min={1}
            nullable
            onNullable={(v) => setHaplotypes({ step: v })}
          />
          <NumberField
            id="hap-max-haplotypes"
            label="Max haplotypes / window"
            help="Safety cap on combinations emitted per window (≥1)."
            value={haplotypes.max_haplotypes_per_window}
            min={1}
            onValue={(v) => setHaplotypes({ max_haplotypes_per_window: v })}
          />
          <NumberField
            id="hap-max-variants"
            label="Max variants / window"
            help="Skip windows with more variant sites than this (≥1)."
            value={haplotypes.max_variants_per_window}
            min={1}
            onValue={(v) => setHaplotypes({ max_variants_per_window: v })}
          />
        </div>
      </Group>

      {/* ----------------------------------------------------------------- */}
      {/* Confirmation                                                      */}
      {/* ----------------------------------------------------------------- */}
      <Group title="Confirmation">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <NumberField
            id="confirm-min-mapped-reads"
            label="Min mapped reads"
            help="Keep haplotypes recruiting at least this many reads (≥1)."
            value={confirm.min_mapped_reads}
            min={1}
            onValue={(v) => setConfirm({ min_mapped_reads: v })}
          />
          <NumberField
            id="confirm-min-identity"
            label="Min identity"
            help="Minimum read-to-haplotype identity, 0–1 (portable assignment)."
            value={confirm.min_identity}
            min={0}
            max={1}
            step={0.01}
            float
            onValue={(v) => setConfirm({ min_identity: v })}
          />
        </div>
      </Group>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Small presentational building blocks                                        //
// --------------------------------------------------------------------------- //

interface GroupProps {
  title: string;
  children: ReactNode;
}

/** A titled card grouping related parameter controls. */
function Group({ title, children }: GroupProps) {
  return (
    <fieldset className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <legend className="px-1 text-sm font-semibold text-slate-800">
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

interface NumberFieldProps {
  id: string;
  label: string;
  help: string;
  value: number | null | undefined;
  min?: number;
  max?: number;
  step?: number;
  /** Treat the value as a float (otherwise it is coerced to an integer). */
  float?: boolean;
  /** Allow a blank value mapping to null; pairs with onNullable. */
  nullable?: boolean;
  disabled?: boolean;
  /** Change handler for required numeric fields. */
  onValue?: (v: number) => void;
  /** Change handler for nullable numeric fields (blank => null). */
  onNullable?: (v: number | null) => void;
}

/**
 * A labelled numeric input with min/max/step bounds and help text. When
 * ``nullable`` is set, an empty field reports ``null`` via ``onNullable``;
 * otherwise non-numeric input is clamped to the minimum (or 0) via ``onValue``.
 */
function NumberField({
  id,
  label,
  help,
  value,
  min,
  max,
  step,
  float = false,
  nullable = false,
  disabled = false,
  onValue,
  onNullable,
}: NumberFieldProps) {
  const helpId = `${id}-help`;

  const handleChange = (raw: string) => {
    if (nullable) {
      if (raw.trim() === "") {
        onNullable?.(null);
        return;
      }
      const n = Math.trunc(Number(raw));
      onNullable?.(Number.isFinite(n) ? n : (min ?? 1));
      return;
    }
    const parsed = float ? Number(raw) : Math.trunc(Number(raw));
    let n = Number.isFinite(parsed) ? parsed : (min ?? 0);
    if (min !== undefined && n < min) n = min;
    if (max !== undefined && n > max) n = max;
    onValue?.(n);
  };

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type="number"
        inputMode={float ? "decimal" : "numeric"}
        value={value ?? ""}
        min={min}
        max={max}
        step={step ?? (float ? "any" : 1)}
        disabled={disabled}
        aria-describedby={helpId}
        onChange={(e) => handleChange(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
      />
      <p id={helpId} className="text-xs text-slate-500">
        {help}
      </p>
    </div>
  );
}

interface TextFieldProps {
  id: string;
  label: string;
  help: string;
  value: string;
  disabled?: boolean;
  onValue: (v: string) => void;
}

/** A labelled free-text input with help text. */
function TextField({
  id,
  label,
  help,
  value,
  disabled = false,
  onValue,
}: TextFieldProps) {
  const helpId = `${id}-help`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        spellCheck={false}
        autoComplete="off"
        disabled={disabled}
        aria-describedby={helpId}
        onChange={(e) => onValue(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
      />
      <p id={helpId} className="text-xs text-slate-500">
        {help}
      </p>
    </div>
  );
}
