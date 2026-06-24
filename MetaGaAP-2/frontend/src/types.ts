// TypeScript mirror of backend/metagaap2/models.py. Keep in sync.

export type EngineKey = "portable" | "native";
export type Aligner = "builtin" | "minimap2" | "bwa_mem2";
export type VariantCaller = "builtin" | "bcftools" | "lofreq";
export type ReferenceMode = "single" | "multiple";
export type StageName = "trim" | "align_call" | "haplotypes" | "confirm" | "merge";
export type StageStatus = "pending" | "running" | "done" | "failed" | "skipped";
export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface ReadGroup {
  sample: string;
  library: string;
  platform: string;
  unit: string;
  id?: string | null;
}

export interface Sample {
  name: string;
  r1: string;
  r2?: string | null;
  reference?: string | null;
  read_group?: ReadGroup | null;
}

export interface QCParams {
  enabled: boolean;
  min_quality: number;
  min_length: number;
  trim_front: number;
  trim_tail: number;
  adapter_fwd?: string | null;
  adapter_rev?: string | null;
  detect_adapters: boolean;
}

export interface VariantParams {
  caller: VariantCaller;
  min_base_quality: number;
  min_mapping_quality: number;
  min_depth: number;
  min_alt_fraction: number;
  ploidy: number;
}

export interface HaplotypeParams {
  window?: number | null;
  max_haplotypes_per_window: number;
  max_variants_per_window: number;
  step?: number | null;
}

export interface ConfirmParams {
  min_mapped_reads: number;
  min_identity: number;
}

export interface RunConfig {
  run_name: string;
  work_dir: string;
  engine: EngineKey;
  aligner: Aligner;
  threads: number;
  reference_mode: ReferenceMode;
  reference?: string | null;
  merge_single_reference: boolean;
  samples: Sample[];
  qc: QCParams;
  variants: VariantParams;
  haplotypes: HaplotypeParams;
  confirm: ConfirmParams;
}

export interface StageResult {
  name: StageName;
  status: StageStatus;
  started_at?: string | null;
  ended_at?: string | null;
  message?: string | null;
  log_path?: string | null;
  outputs: Record<string, string>;
}

export interface SampleResult {
  sample: string;
  stages: StageResult[];
  confirmed_fasta?: string | null;
  stats_csv?: string | null;
  counts_csv?: string | null;
  n_confirmed: number;
  n_haplotypes: number;
}

export interface Job {
  id: string;
  config: RunConfig;
  state: JobState;
  progress: number;
  current_stage?: StageName | null;
  samples: SampleResult[];
  run_dir?: string | null;
  created_at: string;
  started_at?: string | null;
  ended_at?: string | null;
  error?: string | null;
}

export interface ToolInfo {
  name: string;
  found: boolean;
  path?: string | null;
  version?: string | null;
}

export interface EngineCapabilities {
  key: EngineKey;
  label: string;
  available: boolean;
  aligners: Aligner[];
  callers: VariantCaller[];
  missing: string[];
  note?: string | null;
}

export interface ServerInfo {
  version: string;
  platform: string;
  python: string;
  default_engine: EngineKey;
  engines: EngineCapabilities[];
  tools: ToolInfo[];
}

export type WSEventType = "state" | "stage" | "log" | "done";

export interface WSEvent {
  type: WSEventType;
  job_id: string;
  state?: JobState | null;
  progress?: number | null;
  sample?: string | null;
  stage?: StageResult | null;
  line?: string | null;
}

export interface FsEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface FsListing {
  path: string;
  parent?: string | null;
  entries: FsEntry[];
}
