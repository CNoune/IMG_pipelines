# MetaGaAP 2 — Architecture & Build Specification

> This document is the **single source of truth** for the MetaGaAP 2 rebuild.
> Every module is implemented against the contracts defined here and in the
> spine code files (`backend/metagaap2/models.py`, `runner.py`,
> `engines/base.py`, `frontend/src/types.ts`, `frontend/src/api.ts`).
> Read those files for exact signatures before implementing anything.

## 1. What MetaGaAP does (unchanged science)

MetaGaAP is a **reference-guided quasispecies / meta-barcode reconstruction**
pipeline. Given a reference and a set of reads it:

1. **QC/trim** the reads.
2. **Maps** reads to the reference.
3. **Calls variants** against the reference.
4. **Builds a combinatorial haplotype database** — every allele combination
   within a sliding window the size of a read (this is the original
   `biostar175929.jar` step, reimplemented in pure Python).
5. **Re-maps** reads to the haplotype database and keeps haplotypes that
   recruit more than a threshold number of reads ("confirmed sequences").
6. **Multi-sample**: with a single shared reference, merges per-sample
   databases, de-duplicates, then re-maps every sample against the merged DB.

MetaGaAP 2 keeps this method but replaces all Java tools (GATK,
`biostar175929.jar`) and unmaintained tools (FASTX-toolkit, picard), is
non-interactive/reproducible, runs as a **local web app**, and is
**cross-platform** (Windows / Linux / macOS).

## 2. Two-engine architecture

The compute core is abstracted behind an `Engine` interface (see
`engines/base.py`). Two implementations:

### Portable engine — `key = "portable"`
Pure-Python + pip-only wheels available on **all** platforms incl. native
Windows. This is the default and the cross-platform guarantee.

| Stage | Implementation |
|-------|----------------|
| Trim | `cutadapt` (library API) |
| FASTQ/FASTA IO | `dnaio` + `xopen`, `pyfastx` for indexed random access |
| Align | k-mer/minimizer seed index (numpy) + `parasail` semi-global SIMD extension |
| Variant call | builtin frequency pileup caller (`caller = "builtin"`) |
| Haplotype DB | shared pure-Python combinatorial generator (`haplotypes.py`) |
| Confirm/count | k-mer pseudo-assignment of reads to haplotypes |

### Native engine — `key = "native"`
Wraps fast external binaries when present on `PATH` (conda/bioconda on
Linux/macOS; WSL or conda on Windows). Auto-detected; never required.

| Stage | Implementation |
|-------|----------------|
| Trim | `fastp` |
| Align | `minimap2` (default) or `bwa-mem2`, piped to `samtools sort` |
| Variant call | `bcftools mpileup\|call` (`caller="bcftools"`) or `lofreq` (`caller="lofreq"`) |
| Haplotype DB | shared pure-Python combinatorial generator (`haplotypes.py`) |
| Confirm/count | `minimap2`/`bwa` map → `samtools idxstats` |

`haplotypes.py`, `dedup.py`, confirmed-sequence extraction, run-directory
layout, manifest and merging are **engine-independent** pure Python.

### Engine selection
`Engine.detect()` returns availability. The server exposes detected engines
and their capabilities to the UI. The UI offers only callers/aligners the
chosen engine supports. Default = portable; if native binaries are present the
UI lets the user opt into native.

## 3. Repository layout

```
MetaGaAP-2/
  README.md                  # install + usage, both engines, all 3 OSes
  SPEC.md                    # this file
  pyproject.toml             # backend package "metagaap2", deps, console script
  environment.yml            # conda env incl. native binaries (bioconda)
  .gitignore
  backend/
    metagaap2/
      __init__.py            # __version__ = "2.0.0"
      models.py              # SPINE: pydantic models / enums (data contract)
      runner.py              # SPINE: subprocess wrapper (no shell=True), pipes, redirects
      tools.py               # external tool detection (which + version)
      seqio.py               # cross-platform FASTQ/FASTA helpers (dnaio/pyfastx/biopython)
      haplotypes.py          # combinatorial haplotype generator (biostar175929 replacement)
      dedup.py               # checksum de-duplication of FASTA records
      engines/
        __init__.py          # ENGINES registry, get_engine(key), detect_all()
        base.py              # SPINE: Engine ABC + result dataclasses
        portable.py          # pure-Python engine
        native.py            # external-binary engine
      vcf.py                 # minimal pure-Python VCF reader/writer (engine-independent)
      pipeline.py            # orchestrator: per-sample stages, multi-sample merge, manifest
      jobs.py                # in-memory job manager, background execution, progress events
      server.py              # FastAPI app: REST + WebSocket; serves built frontend
      __main__.py            # `python -m metagaap2` -> launch server (+open browser)
    tests/
      test_haplotypes.py     # core science: combinatorial generation correctness
      test_vcf.py
      test_portable_caller.py
      test_runner.py
      test_models.py
  frontend/
    package.json             # React 19, Vite 8, Tailwind 4, TypeScript
    vite.config.ts           # @vitejs/plugin-react + @tailwindcss/vite, proxy /api,/ws
    tsconfig.json
    tsconfig.node.json
    index.html
    src/
      main.tsx
      App.tsx
      index.css              # @import "tailwindcss";  (Tailwind 4 CSS-first)
      types.ts               # SPINE: TS mirror of backend models
      api.ts                 # SPINE: REST + WebSocket client
      lib/format.ts
      components/
        Stepper.tsx
        EngineStatus.tsx     # shows detected engines/tools per machine
        RunConfigForm.tsx    # global run settings (engine, threads, work dir, params)
        SampleSheet.tsx      # add/edit samples (reads, reference, read-group)
        FilePicker.tsx       # server-side path browse (local app) + manual entry
        ParamsPanel.tsx      # QC / variant / haplotype / confirm parameters
        JobProgress.tsx      # live stage progress via WebSocket + logs
        ResultsView.tsx      # per-sample confirmed sequences, stats tables, downloads
```

## 4. Data contract (see `models.py` for the authoritative definitions)

Enums: `EngineKey` {portable, native}; `Aligner` {builtin, minimap2, bwa_mem2};
`VariantCaller` {builtin, bcftools, lofreq}; `ReferenceMode` {single, multiple};
`StageName`; `StageStatus` {pending, running, done, failed, skipped};
`JobState` {queued, running, completed, failed, cancelled}.

Models: `ReadGroup`, `Sample`, `QCParams`, `VariantParams`, `HaplotypeParams`,
`ConfirmParams`, `RunConfig`, `StageResult`, `SampleResult`, `Job`,
`EngineCapabilities`, `ToolInfo`, `ServerInfo`.

## 5. HTTP / WS API (see `api.ts` and `server.py`)

- `GET  /api/health` -> `{status, version}`
- `GET  /api/engines` -> `ServerInfo` (detected engines, tools, platform, defaults)
- `GET  /api/fs?path=` -> directory listing for the in-app file picker (local app)
- `POST /api/jobs` body `RunConfig` -> `Job` (queued)
- `GET  /api/jobs` -> `Job[]`
- `GET  /api/jobs/{id}` -> `Job`
- `POST /api/jobs/{id}/cancel` -> `Job`
- `GET  /api/jobs/{id}/download?path=` -> file stream (results download)
- `WS   /ws/jobs/{id}` -> stream of `{type:"stage"|"log"|"state", ...}` events

## 6. Conventions

- Python ≥ 3.10, type hints everywhere, pydantic v2, `pathlib.Path`.
- **No `shell=True`**; all external commands go through `runner.run`/`run_pipe`
  with list args. Return codes always checked.
- Australian English in user-facing strings; dates DD/MM/YYYY.
- Cross-platform paths (`pathlib`), no hard-coded `/`. Temp via `tempfile`.
- Logging via stdlib `logging`; per-stage log files under the run directory.
- Frontend: React 19 function components + hooks, Tailwind 4 utility classes,
  no class components, no other UI deps required.

## 7. Run directory layout (created by `pipeline.py`)

```
<work_dir>/<run_name>/
  run_config.json          # the exact RunConfig used
  manifest.json            # Job snapshot (stages, outputs, timings)
  logs/<sample>.<stage>.log
  trimmed/<sample>_R1.fastq.gz ...
  alignments/<sample>.bam | .paf
  variants/<sample>.vcf
  haplotypes/<sample>_db.fasta | merged_db.fasta
  results/<sample>_stats.csv, <sample>_confirmed.fasta, <sample>_counts.csv
```

## 8. Dependency lists

Backend runtime (pyproject): `fastapi`, `uvicorn[standard]`, `pydantic>=2`,
`python-multipart`, `cutadapt`, `dnaio`, `xopen`, `pyfastx`, `parasail`,
`numpy`, `biopython`. (All have Win/Linux/macOS py3.13 wheels.)

Native engine (optional, environment.yml / bioconda): `minimap2`, `bwa-mem2`,
`samtools`, `bcftools`, `lofreq`, `fastp`.

Frontend: `react@^19`, `react-dom@^19`, `vite@^8`, `@vitejs/plugin-react@^5`,
`typescript@^5.9`, `tailwindcss@^4`, `@tailwindcss/vite@^4`,
`@types/react@^19`, `@types/react-dom@^19`.
